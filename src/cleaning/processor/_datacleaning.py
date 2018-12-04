#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"cleaning the raw data after bead subraction"
from    typing            import Optional, Dict, Any, List, Tuple, Type, cast
from    itertools         import repeat
from    functools         import partial

import  numpy             as     np

from    utils             import initdefaults
from    model             import Task, Level, PHASE
from    data.views        import BEADKEY
from    control.processor import Processor, ProcessorException
from    ..datacleaning    import DataCleaning

class DataCleaningTask(DataCleaning, Task): # pylint: disable=too-many-ancestors
    "Task for removing incorrect points or cycles or even the whole bead"
    __doc__          = DataCleaning.__doc__
    level            = Level.bead
    hfsigmaphases    = PHASE.initial, PHASE.measure
    populationphases = PHASE.initial, PHASE.measure
    extentphases     = PHASE.initial, PHASE.measure
    pingpongphases   = PHASE.initial, PHASE.measure
    saturationphases = PHASE.initial, PHASE.measure

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self, **kwa)

    def __eq__(self, other):
        return Task.__eq__(self, other)

    @classmethod
    def __ana_default__(cls, right):
        out = cls().__getstate__()
        return ((i, j) for i, j in right if out[i] != j)

    def __getstate__(self):
        state = super().__getstate__()
        state.update(self.__dict__)
        return state

class DataCleaningErrorMessage:
    "creates the error message upon request"
    NAMES = {'saturation': 'non-closing', 'population': '% good',
             'hfsigma':    'σ[HF]',       'extent':     'Δz',
             'pingpong':   '∑|dz|'}
    def __init__(self, stats, cnf:Dict[str,Any], # pylint: disable=too-many-arguments
                 tasktype:Type[DataCleaningTask],
                 beadid: BEADKEY,
                 parents: tuple,
                 ncycles: int = 0) -> None:
        self.stats    = stats
        self.config   = cnf
        self.tasktype = tasktype
        self.beadid   = beadid
        self.parents  = parents
        self.ncycles  = ncycles

    def __str__(self):
        return self.getmessage()

    def __getstate__(self):
        state            = dict(self.__dict__)
        state['parents'] = str(self.parents)
        return state

    def __setstate__(self, info):
        self.__dict__.update(info)

    def data(self) -> List[Tuple[Optional[int], str, str]]:
        "returns a message if the test is invalid"
        dflt = self.tasktype()
        if self.stats is None:
            pop = self.config.get('minpopulation', dflt.minpopulation)
            return [(None, 'population', '< %d' % pop)]

        stats = {i.name: i  for i in self.stats}
        get1  = lambda i, j: len(getattr(stats[i], j))
        get2  = lambda i, j: self.config.get(j+i, getattr(dflt, j+i))
        msg   = (('saturation', '> %.0f%%', 'max'),
                 ('population', '< %.0f%%', 'min'),
                 ('hfsigma',    '< %.4f',   'min'),
                 ('hfsigma',    '> %.4f',   'max'),
                 ('extent',     '< %.2f',   'min'),
                 ('extent',     '> %.2f',   'max'),
                 ('pingpong',   '> %.1f',   'max'))

        vals       = [[get1(i[0], i[-1]), i[0], i[1] % get2(i[0], i[-1])] for i in msg]
        if vals[0][0]:
            cnt        = stats['saturation'].values
            cnt        = cnt[np.isfinite(cnt)]
            vals[0][0] = (cnt > get2('maxdisttozero', "")).sum()
        return [cast(Tuple[Optional[int], str, str], tuple(i)) for i in vals if i[0]]

    def getmessage(self, percentage = False):
        "returns the message"
        data = sorted(self.data(), reverse = True)
        if len(data) == 1 and data[0][0] is None:
            return 'has less than %s %% valid points' % data[0][-1][1:].strip()

        if percentage and self.ncycles > 0:
            templ = '{:.0f}% cycles: {} {}'
            return '\n'.join(templ.format(i[0]/self.ncycles*100, self.NAMES[i[1]], i[2])
                             for i in data)

        templ = '{} cycles: {} {}'
        return '\n'.join(templ.format(i[0], self.NAMES[i[1]], i[2]) for i in data)

    @classmethod
    def message(cls, tasktype, stats, beadid = None, parents = (), **cnf) -> str:
        "returns a message if the test is invalid"
        ncycles = cnf.pop('ncycles', 0)
        return cls(stats, cnf, tasktype, beadid, parents).getmessage(ncycles)

class DataCleaningException(ProcessorException):
    "Exception thrown when a bead is not selected"
    def __str__(self):
        args = self.args[0] # pylint: disable=unsubscriptable-object
        return f"{args.parents}: {args.beadid}\n{args}"

class DataCleaningProcessor(Processor[DataCleaningTask]):
    "Processor for cleaning the data"
    __DFLT = DataCleaningTask()
    @classmethod
    def __get(cls, name, cnf):
        return cnf.get(name, getattr(cls.__DFLT, name))

    @classmethod
    def __exc(cls, val, cnf, info, frame):
        "creates the exception"
        ncy = getattr(frame.track, 'ncycles', 0)
        msg = DataCleaningErrorMessage(val, cnf, cls.tasktype, info[0], frame.parents, ncy)
        return DataCleaningException(msg, 'warning')

    @classmethod
    def __test(cls, frame, bead, cnf):
        phases = frame.track.phase.select
        sel    = cls.tasktype(**cnf)
        pha    = cycs = None
        for name in sel.CYCLES:
            cur = cls.__get(name+'phases', cnf)
            if cycs is None or pha != cur:
                pha, cycs = cur, (phases(..., cur[0]), phases(..., cur[1]+1))
            yield getattr(sel, name)(bead, *cycs)

        cur = cls.__get('saturationphases', cnf)
        tmp = (phases(..., i) for i in (cur[0], cur[0]+1, cur[1], cur[1]+1))
        yield sel.saturation(bead, *tmp)

    @classmethod
    def _compute(cls, cnf, frame, info):
        info = info[0], np.copy(info[1])
        res  = cls.compute(frame, info, **cnf)
        if isinstance(res, Exception):
            raise res # pylint: disable=raising-bad-type
        return info

    @classmethod
    def compute(cls, frame, info, cache = None, **cnf) -> Optional[DataCleaningException]:
        "returns the result of the beadselection"
        tested = False
        if cache is not None:
            val, discard = cache.get(info[0], ('', False))
            if discard:
                return cls.__exc(val, cnf, info, frame)
            tested       = val != ''

        discard = DataCleaning(**cnf).aberrant(info[1])
        if not tested:
            val  = tuple(cls.__test(frame, info[1], cnf))

        if not discard:
            bad = cls.tasktype.badcycles(val) # type: ignore
            if len(bad):
                for _, cyc in frame.track.view("cycles",
                                               data     = {info[0]: info[1]},
                                               selected = zip(repeat(info[0]), bad)):
                    cyc[:] = np.NaN

                if not tested:
                    minpop  = 1.-cls.__get('minpopulation', cnf)*1e-2
                    discard = np.isnan(info[1]).sum() > len(info[1]) * minpop

        if not (tested or cache is None):
            cache[info[0]] = val, discard
        if discard:
            return cls.__exc(val, cnf, info, frame)
        return None

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        return toframe.withaction(partial(cls._compute, cnf))

    def run(self, args):
        "updates the frames"
        cache = args.data.setCacheDefault(self, dict())
        return args.apply(partial(self.apply, cache = cache, **self.config()))
