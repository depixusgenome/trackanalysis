#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"cleaning the raw data after bead subraction"
from    collections  import namedtuple
from    dataclasses  import dataclass
from    itertools    import repeat
from    functools    import partial
from    typing       import (
    Any, Dict, Iterator, List, Optional, Tuple, Type, ClassVar, cast, TypeVar
)

import  numpy             as     np

from    taskcontrol.processor   import Processor, ProcessorException
from    taskmodel               import Task, Level, PHASE, InstrumentType
from    utils                   import initdefaults

from    ..names                 import NAMES
from    .._core                 import (   # pylint: disable=import-error
    DataCleaning, Partial, AberrantValuesRule
)
from    ..rampcleaningrules     import ExtentOutliersRule


class DataCleaningTaskBase(Task, zattributes = DataCleaning.zscaledattributes()):
    "Base-Task for removing incorrect points or cycles or even the whole bead"
    __doc__          = getattr(DataCleaning, '__doc__', None)

    hfsigmaphases:     Tuple[int, int] = (PHASE.initial, PHASE.measure)
    populationphases:  Tuple[int, int] = (PHASE.initial, PHASE.measure)
    extentphases:      Tuple[int, int] = (PHASE.initial, PHASE.measure)
    pingpongphases:    Tuple[int, int] = (PHASE.initial, PHASE.measure)
    phasejumpphases:   Tuple[int, int] = (PHASE.initial, PHASE.measure)
    saturationphases:  Tuple[int, int] = (PHASE.initial, PHASE.measure)
    locals().update(DataCleaning().config())

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    level:                  ClassVar[Level]          = Level.bead
    PRE_CORRECTION_CYCLES:  ClassVar[Tuple[str,...]] = ('phasejump',)
    POST_CORRECTION_CYCLES: ClassVar[Tuple[str,...]] = (
        'population', 'hfsigma', 'extent', 'pingpong'
    )

    @property
    def core(self) -> DataCleaning:
        "return the c++ object"
        tmp = DataCleaning()
        tmp.configure(self.__dict__)
        return tmp

    @staticmethod
    def badcycles(stats) -> np.ndarray:
        "returns all bad cycles"
        bad = np.empty(0, dtype = 'i4')
        if stats is None:
            return bad
        for stat in stats.values() if isinstance(stats, dict) else stats:
            bad = np.union1d(bad, stat.min)
            bad = np.union1d(bad, stat.max)
        return bad

class RampDataCleaning(DataCleaning):
    "Removing aberrant points and cycles in Ramps"

    def __init__(self, **kwa):
        self.extentoutliers: ExtentOutliersRule = kwa.get('extentoutliers', ExtentOutliersRule())
        super().__init__(**kwa)

    def configure(self, **kwa):
        "Configure the contained Rules"
        super().configure(kwa)
        self.extentoutliers.configure(**kwa)

class DataCleaningTask(DataCleaningTaskBase):
    "Task for removing incorrect points or cycles or even the whole bead"

class RampDataCleaningTask(DataCleaningTaskBase):
    "Task for removing incorrect points or cycles or even the whole bead in Ramp-experiments"
    extentoutliersphases:     Tuple[int, int] = (PHASE.initial, PHASE.measure)

    locals().update(ExtentOutliersRule().config())

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        """
        Parameters
        ----------
        Following parameters configure the contained rules:

        **extentoutliers**
        extentoutlierspercentile : float
            the percentile to consider as consensus
        minextentoutliers : float
            the minimum accepted extent, relative to the consensus
        maxextentoutliers : float
            the maximum accepted extent, relative to the consensus
        """
        super().__init__(**kwa)

    PRE_CORRECTION_CYCLES:  ClassVar[Tuple[str, ...]] = DataCleaningTaskBase.PRE_CORRECTION_CYCLES
    POST_CORRECTION_CYCLES: ClassVar[Tuple[str, ...]] = (DataCleaningTaskBase.POST_CORRECTION_CYCLES
                                                         + ('extentoutliers',))

    @property
    def core(self) -> RampDataCleaning:
        tmp = RampDataCleaning()
        tmp.configure(**self.__dict__)
        return tmp

class DataCleaningErrorMessage:
    "creates the error message upon request"
    def __init__(self, stats, cnf:Dict[str,Any],  # pylint: disable=too-many-arguments
                 tasktype:Type[DataCleaningTask],
                 beadid:  int,
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
        if not self.stats:
            pop = self.config.get('minpopulation', dflt.minpopulation)
            return [(None, 'population', '< %d' % pop)]
        stats = {i.name: i  for i in self.stats}
        getcount = lambda prefix, name: len(getattr(stats[name], prefix))
        getcnf   = lambda prefix, name: self.config.get(prefix+name, getattr(dflt, prefix+name))

        param      = namedtuple('param', ['name', 'format', 'prefix'])
        parameters = (param('saturation',     '> %.0f%%', 'max'),
                      param('population',     '< %.0f%%', 'min'),
                      param('hfsigma',        '< %.4f',   'min'),
                      param('hfsigma',        '> %.4f',   'max'),
                      param('extent',         '< %.2f',   'min'),
                      param('extent',         '> %.2f',   'max'),
                      param('pingpong',       '> %.1f',   'max'),
                      param('phasejump',      '> %.1f',   'max'),
                      param('extentoutliers', '< %.0f%% of Δz-consensus', 'min'))

        errmsg = [[getcount(i.prefix, i.name), i.name, i.format % getcnf(i.prefix, i.name)]
                  for i in parameters
                  if i.name in stats.keys()]  # only generate messages for valid rules
        if errmsg[0][0]:
            cnt          = stats['saturation'].values
            cnt          = cnt[np.isfinite(cnt)]
            errmsg[0][0] = (cnt > getcnf("", 'maxdisttozero')).sum()
        return [cast(Tuple[Optional[int], str, str], tuple(i)) for i in errmsg if i[0]]

    def getmessage(self, percentage = False):
        "returns the message"
        data = sorted(self.data(), reverse = True)
        if len(data) == 1 and data[0][0] is None:
            return 'has less than %s %% valid points' % data[0][-1][1:].strip()

        if percentage and self.ncycles > 0:
            templ = '{:.0f}% cycles: {} {}'
            return '\n'.join(templ.format(i[0]/self.ncycles*100, NAMES[i[1]], i[2])
                             for i in data)

        templ = '{} cycles: {} {}'
        return '\n'.join(templ.format(i[0], NAMES[i[1]], i[2]) for i in data)

    @classmethod
    def message(cls, tasktype, stats, beadid = None, parents = (), **cnf) -> str:
        "returns a message if the test is invalid"
        ncycles = cnf.pop('ncycles', 0)
        return cls(stats, cnf, tasktype, beadid, parents).getmessage(ncycles)

class DataCleaningException(ProcessorException):
    "Exception thrown when a bead is not selected"
    def __str__(self):
        args = self.args[0]  # pylint: disable=unsubscriptable-object
        return f"{args.parents}: {args.beadid}\n{args}"

    def shortmessage(self):
        "return the shorter message"
        return str(self.args[0])  # pylint: disable=unsubscriptable-object

    def errkey(self) -> str:
        "return an indicator of the type of error"
        # pylint: disable=unsubscriptable-object
        return max(self.args[0].data(), default = ('', 'unknown'))[1]

@dataclass
class CleaningCacheData:
    "the data saved from call to call for each bead"
    errors:  Tuple[Partial,...]
    discard: bool
    mask:    np.ndarray

    def __iter__(self):
        return iter((self.errors, self.discard, self.mask))

    def __getitem__(self, val: int):
        return (self.errors, self.discard, self.mask)[val]

    def apply(self, cnf, frame, info):
        "reapply the previous work"
        if self.discard:
            val = tuple(i for i in self.errors if hasattr(DataCleaning, i.name))
            return DataCleaningProcessor.exc(val, cnf, info, frame)

        info[1][self.mask] = np.NaN
        return None


CleaningTaskType = TypeVar('CleaningTaskType', bound = DataCleaningTaskBase)


class DataCleaningProcessorBase(Processor[CleaningTaskType]):
    "Processor for cleaning the data"
    tasktype: Type[DataCleaningTaskBase]  # type: ignore

    @classmethod
    def __get(cls, name, cnf):
        return cnf.get(name, getattr(cls.tasktype, name))

    @classmethod
    def exc(cls, val, cnf, info, frame):
        "creates the exception"
        ncy = getattr(frame.track, 'ncycles', 0)
        msg = DataCleaningErrorMessage(val, cnf, cls.tasktype, info[0], frame.parents, ncy)
        return DataCleaningException(msg, 'warning')

    @staticmethod
    def _doesapply(rulename: str, frame) -> bool:
        if rulename == 'phasejump':
            return frame.track.instrument['type'] is InstrumentType.sdi
        return True

    @classmethod
    def __precorrectiontest(cls, frame, bead, cnf) -> Iterator[Partial]:
        phases = frame.track.phase.select
        sel    = cls.tasktype(**cnf).core
        pha    = cycs = None
        rules = (
            name for name in cls.tasktype.PRE_CORRECTION_CYCLES
            if cls._doesapply(name, frame)
        )
        for name in rules:
            cur = cls.__get(name+'phases', cnf)
            if cycs is None or pha != cur:
                pha, cycs = cur, (phases(..., cur[0]), phases(..., cur[1]+1))
            yield getattr(sel, name)(bead, *cycs)

    @classmethod
    def __postcorrectiontest(cls, frame, bead, cnf) -> Iterator[Partial]:
        phases = frame.track.phase.select
        sel    = cls.tasktype(**cnf).core
        pha    = cycs = None
        rules = (
            name for name in cls.tasktype.POST_CORRECTION_CYCLES
            if cls._doesapply(name, frame)
        )
        for name in rules:
            cur = cls.__get(name+'phases', cnf)
            if cycs is None or pha != cur:
                pha, cycs = cur, (phases(..., cur[0]), phases(..., cur[1]+1))
            yield getattr(sel, name)(bead, *cycs)

        cur = cls.__get('saturationphases', cnf)
        tmp = (phases(..., i) for i in (cur[0], cur[0]+1, cur[1], cur[1]+1))
        yield sel.saturation(bead, *tmp)

    @classmethod
    def __removebadcycles(cls, frame, cnf, val, arr):
        bad = cls.tasktype.badcycles(val)
        if len(bad):
            for _, cyc in frame.track.view(
                    "cycles",
                    data     = {0: arr},
                    selected = zip(repeat(0), bad)
            ):
                cyc[:] = np.NaN

            maxnanrate  = 1.-cls.__get('minpopulation', cnf)*1e-2
            return np.isnan(arr).sum() > len(arr) * maxnanrate
        return False

    @classmethod
    def _compute(cls, cnf, frame, info):
        info = info[0], np.copy(info[1])
        res  = cls.compute(frame, info, **cnf)
        if isinstance(res, Exception):
            raise res  # pylint: disable=raising-bad-type
        return info

    @classmethod
    def compute(cls, frame, info, cache = None, **cnf) -> Optional[DataCleaningException]:
        "returns the result of the beadselection"
        bead, arr = info
        if cache is not None:
            cur = cache.get(bead, None)
            if cur:
                return cur.apply(cnf, frame, info)

        val       = tuple(cls.__precorrectiontest(frame, arr, cnf))
        tmp       = AberrantValuesRule(**cnf)
        discard   = tmp.aberrant(arr, False, cls.__get('minpopulation', cnf)*1e-2)
        val      += tuple(cls.__postcorrectiontest(frame, arr, cnf))

        if not discard:
            discard = cls.__removebadcycles(frame, cnf, val, arr)

        if cache is not None:
            cache[bead] = CleaningCacheData(val, discard, np.isnan(arr))

        return cls.exc(val, cnf, info, frame) if discard else None

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        return toframe.withaction(partial(cls._compute, cnf))

    def run(self, args):
        "updates the frames"
        cache = args.data.setcachedefault(self, dict())
        return args.apply(partial(self.apply, cache = cache, **self.config()))

class DataCleaningProcessor(DataCleaningProcessorBase[DataCleaningTask]):
    "Processor for cleaning the data"

class RampDataCleaningProcessor(DataCleaningProcessorBase[RampDataCleaningTask]):
    "Processor for cleaning the data"
