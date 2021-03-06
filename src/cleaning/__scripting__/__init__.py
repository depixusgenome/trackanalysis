#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=function-redefined
"""
Monkey patches the Track class.

Adds a method for discarding beads with Cleaning warnings
"""
from   copy                             import copy as shallowcopy
from   concurrent.futures               import ProcessPoolExecutor
from   typing                           import (Dict, Optional, Iterator, List, Any,
                                                Set, Union, Tuple, Sequence, cast)
import numpy                            as     np
import pandas                           as     pd

from   data.views                       import Beads, Cycles
from   data.trackops                    import dropbeads
from   data.__scripting__.track         import Track
from   data.__scripting__.tracksdict    import TracksDict
from   utils.decoration                 import addproperty, addto
from   taskcontrol.processor.dataframe  import DataFrameFactory
from   taskmodel.__scripting__          import Tasks, Task
from   taskmodel.__scripting__.track    import LocalTasks
from   ..processor                      import (DataCleaningProcessor,
                                                DataCleaningErrorMessage,
                                                BeadSubtractionTask,
                                                BeadSubtractionProcessor,
                                                DataCleaningException)
from   ..beadsubtraction                import  FixedBeadDetection

@addto(BeadSubtractionTask, staticmethod)
def __scripting_save__() -> bool:
    return False

class BeadSubtractionDescriptor:
    "A descriptor for adding subtracted beads"
    NAME    = Tasks(BeadSubtractionTask).name
    __doc__ = BeadSubtractionTask.__doc__

    def __get__(
            self, inst, owner
    ) -> Union['BeadSubtractionDescriptor', Optional[BeadSubtractionTask]]:
        return self if inst is None else inst.tasks.get(self.NAME, None)

    def __delete__(self, inst):
        inst.tasks.pop(self.NAME, None)

    def __set__(self, inst,
                beads: Union[None, Dict[str,Any], BeadSubtractionTask, Sequence[int]]):
        tpe = BeadSubtractionTask
        lst = (beads.get('beads', None)                 if isinstance(beads, dict) else
               cast(BeadSubtractionTask, beads).beads   if isinstance(beads, tpe)  else
               [cast(int, beads)]                       if np.isscalar(beads)      else
               []                                       if beads is None           else
               cast(Sequence[int], beads))

        if not beads:
            inst.tasks.pop(self.NAME, None)
        elif isinstance(beads, dict):
            inst.tasks[self.NAME] = BeadSubtractionTask(**beads)
        elif isinstance(beads, BeadSubtractionTask):
            inst.tasks[self.NAME] = beads
        else:
            inst.tasks.setdefault(self.NAME, BeadSubtractionTask()).beads = list(lst)


LocalTasks.subtraction = BeadSubtractionDescriptor()  # type: ignore

@addproperty(Track, 'cleaning')
class TrackCleaningScript:
    """
    Provides methods for finding beads with cleaning warnings and possibly
    discarding them:

    * `track.cleaning.good()`: lists good beads
    * `track.cleaning.bad()`: lists bad beads
    * `track.cleaning.messages()`: lists all messages
    * `track.cleaning.dropbad()`: returns a track with only good beads loaded.
    * `track.cleaning.concatenate(othertrack)`: returns a track combining the 2
    tracks used when an experiment is resumed.
    """
    def __init__(self, track: Track) -> None:
        self.track = track

    def process(self,
                beads: Sequence[int] = None,
                **kwa) -> Dict[int, Optional[DataCleaningErrorMessage]]:
        "returns a dictionnary of cleaning results"
        get  = lambda x: x if x is None else x.args[0]  # noqa

        itms = self.track.beads
        sub  = self.track.tasks.subtraction  # type: ignore
        if sub is not None:
            cache: dict = {}
            itms        = BeadSubtractionProcessor.apply(itms, cache = cache, **sub.config())
        itms = itms[list(beads)] if beads else itms

        dfltask = self.track.tasks.cleaning  # type: ignore
        if dfltask is None:
            dfltask = Tasks.cleaning(instrument = self.track.instrument['type'])

        # use the default settings for this track
        dflt = dfltask.config()
        dflt.update(kwa)
        kwa  = dflt

        return {info[0]: get(DataCleaningProcessor.compute(itms, info, **kwa))
                for info in cast(Iterator, itms)}

    def good(self, beads: Sequence[int] = None, **kwa) -> List[int]:
        "returns beads without warnings"
        return [i for i, j in self.process(beads, **kwa).items() if j is None]

    def bad(self, beads: Sequence[int] = None, **kwa) -> List[int]:
        "returns beads with warnings"
        return [i for i, j in self.process(beads, **kwa).items() if j is not None]

    def fixed(self,
              beads: Sequence[int] = None,
              output  = 'beads',
              **kwa) -> List[int]:
        "a list of potential fixed beads"
        alg  = FixedBeadDetection(**kwa)
        data = self.track.beads[list(beads)] if beads else self.track.beads
        return (alg.dataframe(data) if output == 'dataframe' else
                alg(data)           if output == "values"    else
                [i[-1] for i in alg(data)])

    def messages(self,  # pylint: disable = too-many-locals
                 beads: Sequence[int] = None,
                 forceclean               = False,
                 **kwa) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        ids:   List[int] = []
        types: List[str] = []
        cycs:  List[int] = []
        msgs:  List[str] = []

        if forceclean or self.track.cleaned is False:  # type: ignore
            if beads:
                good = set(self.track.beads.keys())
                cur: Optional[List[int]] = [i for i in beads if i in good]
            else:
                cur                      = None
            for i, j in self.process(cur, **kwa).items():
                if j is None:
                    continue
                itms = j.data()

                cycs .extend([i[0] for i in itms])
                types.extend([i[1] for i in itms])
                msgs .extend([i[2] for i in itms])
                ids.extend((cast(int, i),)*(len(msgs)-len(ids)))

        miss = list(set(beads)-set(self.track.beads.keys())) if beads else []
        cycs .extend([self.track.ncycles]*len(miss))
        types.extend(['missing']*len(miss))
        msgs .extend([''] * len(miss))
        ids.extend(cast(List[int], miss))

        name = np.full(len(ids), DataFrameFactory.trackname(self.track))
        date = np.full(len(ids), getattr(self.track, 'pathinfo').modification)
        return pd.DataFrame({'key':          name,
                             'modification': date,
                             'bead':         np.array(ids, dtype = 'i4'),
                             'types':        types,
                             'cycles':       np.array(cycs, dtype = 'i4'),
                             'message':      msgs}).set_index(['bead', 'key'])

    def dataframe(self, beads: Sequence[int] = None, **kwa) -> Optional[pd.DataFrame]:
        """
        return a dataframe with all test values
        """
        if beads:
            good                     = set(self.track.beads.keys())
            cur: Optional[List[int]] = [i for i in beads if i in good]
        else:
            cur  = None

        cache: dict = {}
        tuple(self.process(cur, cache = cache, **kwa))
        if len(cache) == 0:
            return None

        name       = DataFrameFactory.trackname(self.track)
        info: dict = {'track': [], 'bead': [], 'cycle': []}
        info.update((i.name, []) for i in next(iter(cache.values()))[0])
        for beadid, (vals, _) in cache.items():
            info['bead'].append(np.full(self.track.ncycles, beadid, dtype = 'i4'))
            info['track'].append(np.full(self.track.ncycles, name))
            info['cycle'].append(np.arange(self.track.ncycles, dtype = 'i4'))
            for stat in vals:
                info[stat.name].append(stat.values)

        frame  = pd.DataFrame({i: np.concatenate(j) for i, j in info.items()})
        frame['modification'] = getattr(self.track, 'pathinfo').modification
        return frame

    def dropbad(self, **kwa) -> Track:
        "removes bad beads *forever*"
        return dropbeads(self.track, *self.bad(**kwa))  # type: ignore

@addproperty(TrackCleaningScript, 'data')
class TrackCleaningScriptData:
    """
    Provides access to certain classes of beads:

    * `track.cleaning.data.fixed`: `Beads` for fixed beads only
    * `track.cleaning.data.subtraction`: `Beads` for subtraction beads only. The
    resulting subtracted bead is displayed with id -1.
    * `track.cleaning.data.bad`: `Beads` for bad beads only
    * `track.cleaning.data.good`: `Beads` for good beads only
    """
    def __init__(self, itm):
        self.track = itm.track

    def fixedspread(self, bead, **kwa) -> np.ndarray:
        """
        return the spread of the fixed bead
        """
        return FixedBeadDetection(**kwa).cyclesock((self.track.beads, bead))

    def fixed(self, **kwa) -> Cycles:
        "displays aligned cycles for fixed beads only"
        beads = self.track.cleaning.fixed(**kwa)
        return self.track.apply(Tasks.alignment)[beads,...]

    def bad(self, **kwa) -> Cycles:
        "displays aligned cycles for bad beads only"
        beads = self.track.cleaning.bad(**kwa)
        return self.track.apply(Tasks.alignment)[beads,...]

    def good(self, **kwa) -> Cycles:
        "displays aligned cycles for good beads only"
        beads = self.track.cleaning.good(**kwa)
        return self.track.apply(Tasks.alignment)[beads,...]

    def subtraction(self, beads = None, **kwa) -> Optional[Beads]:
        "displays aligned cycles for subtracted beads only"
        task = self.track.tasks.subtraction
        if task is None and beads is None:
            beads = self.track.cleaning.fixed(**kwa)

        if beads is None:
            beads = getattr(task, 'beads', None)
            if not beads:
                return None
            cnf = task.config()

        elif task is None:
            cnf          = cast(Task, Tasks.subtraction(beads = beads)).config()
        else:
            cnf          = task.config()
            cnf['beads'] = beads
        cnf.update(**kwa)

        proc     = Tasks.subtraction.processor(**cnf)
        data     = {i: self.track.data[i] for i in beads}
        data[-1] = proc.signal(self.track.beads)  # type: ignore
        return self.track.apply(Tasks.alignment).withdata(data)


if isinstance(TrackCleaningScript.__doc__, str):
    TrackCleaningScript.__doc__ = (
        TrackCleaningScript.__doc__[:-5]
        + """
        * `track.cleaning.data` p"""
        + TrackCleaningScriptData.__doc__.split('\n')[1].strip()[1:] + "\n"  # type: ignore
        + '\n   '
        .join(TrackCleaningScriptData.__doc__.split('\n')[2:])  # type: ignore
        .replace('\n', '\n    ')
    )
    Track.__doc__ += (  # type: ignore
        """
        * `cleaning` p"""
        + TrackCleaningScript.__doc__.split('\n')[1].strip()[1:]+"\n"
        + TrackCleaningScript.__doc__.split('\n')[2]+"\n"
        + '\n'.join(TrackCleaningScript.__doc__.split('\n')[3:]).replace('\n', '\n    ')
    )

@addproperty(getattr(TracksDict, '__base__'), 'cleaning')
class TracksDictCleaningScript:
    """
    Adds means for finding beads with cleaning warnings and possibly discarding
    them. One can do:

    * `tracks.cleaning.good()`: lists beads which are good throughout all tracks
    * `tracks.cleaning.bad()`: lists beads bad at least in one track
    * `tracks.cleaning.messages()`: lists all messages
    * `tracks.cleaning.dropbad()`: returns a *TracksDict* with tracks with only
    good beads loaded.
    """
    def __init__(self, tracks: TracksDict) -> None:
        self.tracks = tracks

    def process(self,
                beads: Sequence[int] = None,
                **kwa) -> Tuple[Set[int], Set[int]]:
        "returns beads without warnings"
        good: Set[int] = set(self.tracks.commonbeads())
        bad:  Set[int] = (set(self.tracks.availablebeads()) - good)
        cur:  Set[int] = (bad | good) if beads is None else set(beads)
        for track in self.tracks.values():
            tmp = (set(track.beads.keys())-bad) & cur
            if tmp:
                bad.update(track.cleaning.bad(tmp,**kwa))
        return bad & cur, (good-bad) & cur

    @staticmethod
    def _compute(args) -> pd.DataFrame:
        "return messages"
        itm = TrackCleaningScript(Track(**args[0]))
        return getattr(itm, args[1])(*args[2:-1], **args[-1])

    def __compute(self, name, beads, *args) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        if beads is None:
            beads = self.tracks.availablebeads()

        itr  = (
            (
                {
                    j: getattr(i, j)
                    for j in ('path', 'key', '_modificationdate')
                    if hasattr(i, j)
                },
                name, beads
            )+args
            for i in self.tracks.values()
        )
        with ProcessPoolExecutor() as pool:
            items = list(pool.map(self._compute, itr))
        return pd.concat(items)

    def messages(self,
                 beads: Sequence[int] = None,
                 forceclean               = False,
                 **kwa) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        return self.__compute('messages', beads, forceclean, kwa)

    def dataframe(self, beads: Sequence[int] = None, **kwa) -> Optional[pd.DataFrame]:
        """
        return a dataframe with all test values
        """
        return self.__compute('dataframe', beads, kwa)

    def good(self, **kwa) -> List[int]:
        "returns beads without warnings"
        return sorted(self.process(**kwa)[1])

    def bad(self, **kwa) -> List[int]:
        "returns beads with warnings"
        return sorted(self.process(**kwa)[0])

    def dropbad(self, **kwa) -> TracksDict:
        "removes bad beads *forever*"
        cpy = self.tracks[...]
        for key, track in cpy.items():
            cpy[key] = TrackCleaningScript(track).dropbad(**kwa)
        return cpy

    @staticmethod
    def _subtractbeads(info):
        return (info[0], info[1](info[2].beads))

    def subtractbeads(self, **kwa) -> TracksDict:
        "creates a new TracksDict with subtracted beads"
        alg = FixedBeadDetection(**kwa)
        itr = ((i, alg, j) for i, j in self.tracks.items())
        with ProcessPoolExecutor() as pool:
            info = dict(pool.map(self._subtractbeads, itr))

        itms = cast(TracksDict, type(self.tracks)())
        for i, beads in info.items():
            itms[i] = shallowcopy(self.tracks[i])
            itms[i].tasks.subtraction = [j[-1] for j in beads]
        return itms


if isinstance(TracksDict.__doc__, str):
    TracksDict.__doc__ += (
        """
        ## Cleaning

        """
        + str(TracksDictCleaningScript.__doc__)
    )
    TracksDict.__base__.__doc__ = str(TracksDict.__doc__)

@addto(TracksDict)                      # type: ignore
def basedataframe(
        self,
        loadall  = False,
        cleaning = None,
        fixed    = None,
        __old__  = TracksDict.basedataframe
) -> pd.DataFrame:
    "Returns a table with some data on the track files"
    frame = __old__(self, loadall)
    info  = dict(
        {i: np.full(frame.shape[0], None, dtype = 'O') for i in ('good', 'bad', 'fixed')},
        key = np.array(list(self.keys()), dtype = frame['key'].values.dtype)
    )

    for ind, track in enumerate(self.values()):
        if track.isloaded or loadall:
            script = TrackCleaningScript(track)
            out    = script.process(**(
                {}       if cleaning is None           else
                cleaning if isinstance(cleaning, dict) else
                cleaning.config()
            ))
            if out:
                info['good'][ind] = [i for i,j in out.items() if j is None]
                info['bad'][ind]  = [i for i,j in out.items() if j is not None]
            info['fixed'][ind] = script.fixed(**(
                {}       if fixed is None           else
                fixed if isinstance(fixed, dict) else
                fixed.config()
            ))

    return frame.join(pd.DataFrame(info).set_index('key'), on = 'key')


__all__: Tuple[str, ...] = ()
