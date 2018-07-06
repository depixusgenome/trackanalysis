#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=function-redefined
"""
Monkey patches the Track class.

Adds a method for discarding beads with Cleaning warnings
"""
from   copy                             import deepcopy
from   typing                           import (Dict, Optional, Iterator, List, Any,
                                                Set, Union, Tuple, Sequence, cast)
import numpy                            as     np
import pandas                           as     pd
from   utils.decoration                 import addproperty, addto
from   control.processor.dataframe      import DataFrameFactory
from   model.__scripting__              import Tasks
from   model.__scripting__.track        import LocalTasks
from   data.views                       import BEADKEY, Beads, Cycles
from   data.trackops                    import dropbeads
from   data.__scripting__.track         import Track
from   data.__scripting__.tracksdict    import TracksDict
from   ..processor                      import (DataCleaningProcessor,
                                                DataCleaningErrorMessage)
from   ..beadsubtraction                import (BeadSubtractionTask,
                                                BeadSubtractionProcessor,
                                                FixedBeadDetection)

@addto(BeadSubtractionTask, staticmethod)
def __scripting_save__() -> bool:
    return False

class BeadSubtractionDescriptor:
    "A descriptor for adding subtracted beads"
    NAME    = Tasks(BeadSubtractionTask).name
    __doc__ = BeadSubtractionTask.__doc__

    def __get__(self, inst, owner
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

LocalTasks.subtraction = BeadSubtractionDescriptor() # type: ignore

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
                beads: Sequence[BEADKEY] = None,
                **kwa) -> Dict[BEADKEY, Optional[DataCleaningErrorMessage]]:
        "returns a dictionnary of cleaning results"
        get  = lambda x: x if x is None else x.args[0]

        itms = self.track.beads
        sub  = self.track.tasks.subtraction # type: ignore
        if sub is not None:
            cache: dict = {}
            itms        = BeadSubtractionProcessor.apply(itms, cache = cache, **sub.config())
        itms = itms[list(beads)] if beads else itms

        dfltask = self.track.tasks.cleaning  # type: ignore
        if dfltask is None:
            dfltask = Tasks.cleaning()

        # use the default settings for this track
        dflt = dfltask.config()
        dflt.update(kwa)
        kwa  = dflt

        return {info[0]: get(DataCleaningProcessor.compute(itms, info, **kwa))
                for info in cast(Iterator, itms)}

    def good(self, beads: Sequence[BEADKEY] = None, **kwa) -> List[BEADKEY]:
        "returns beads without warnings"
        return [i for i, j in self.process(beads, **kwa).items() if j is None]

    def bad(self, beads: Sequence[BEADKEY] = None, **kwa) -> List[BEADKEY]:
        "returns beads with warnings"
        return [i for i, j in self.process(beads, **kwa).items() if j is not None]

    def fixed(self,
              beads: Sequence[BEADKEY] = None,
              output  = 'beads',
              **kwa) -> List[int]:
        "a list of potential fixed beads"
        alg  = FixedBeadDetection(**kwa)
        data = self.track.beads[list(beads)] if beads else self.track.beads
        return (alg.dataframe(data) if output == 'dataframe' else
                alg(data)           if output == "values"    else
                [i[-1] for i in alg(data)])

    def messages(self,  # pylint: disable = too-many-locals
                 beads: Sequence[BEADKEY] = None,
                 forceclean               = False,
                 **kwa) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        ids   = [] # type: List[int]
        types = [] # type: List[str]
        cycs  = [] # type: List[int]
        msgs  = [] # type: List[str]

        if forceclean or self.track.cleaned is False: # type: ignore
            if beads:
                good = set(self.track.beads.keys())
                cur  = [i for i in beads if i in good]
            else:
                cur  = None
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
        msgs .extend([''] *len(miss))
        ids.extend(cast(List[int], miss))

        name = DataFrameFactory.trackname(self.track)
        return pd.DataFrame(dict(key     = np.full(len(ids), name),
                                 bead    = np.array(ids, dtype = 'i4'),
                                 types   = types,
                                 cycles  = np.array(cycs, dtype = 'i4'),
                                 message = msgs)).set_index(['bead', 'key'])

    def dataframe(self, beads: Sequence[BEADKEY] = None, **kwa) -> Optional[pd.DataFrame]:
        """
        return a dataframe with all test values
        """
        if beads:
            good = set(self.track.beads.keys())
            cur  = [i for i in beads if i in good]
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

        return pd.DataFrame({i: np.concatenate(j) for i, j in info.items()})

    def dropbad(self, **kwa) -> Track:
        "removes bad beads *forever*"
        return dropbeads(self.track, *self.bad(**kwa)) # type: ignore

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
        if beads is None:
            beads = getattr(task, 'beads', None)
            if not beads:
                return None
            cnf = task.config()

        elif task is None:
            cnf = Tasks.beadsubtraction(bead = beads) # type: ignore

        else:
            cnf          = task.config()
            cnf['beads'] = beads
        cnf.update(**kwa)

        proc     = Tasks.subtraction.processor(**cnf)
        data     = {i: self.track.data[i] for i in beads}
        data[-1] = proc.signal(self.track.beads) # type: ignore
        return self.track.apply(Tasks.alignment).withdata(data)

TrackCleaningScript.__doc__ = (
    TrackCleaningScript.__doc__[:-5]
    +"""
    * `track.cleaning.data` p"""
    +TrackCleaningScriptData.__doc__.split('\n')[1].strip()[1:]+"\n"
    +'\n   '.join(TrackCleaningScriptData.__doc__.split('\n')[2:]).replace('\n', '\n    ')
    )
Track.__doc__ += (
    """
    * `cleaning` p"""
    +TrackCleaningScript.__doc__.split('\n')[1].strip()[1:]+"\n"
    +TrackCleaningScript.__doc__.split('\n')[2]+"\n"
    +'\n'.join(TrackCleaningScript.__doc__.split('\n')[3:]).replace('\n', '\n    ')
    )

@addproperty(TracksDict.__base__, 'cleaning')
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
                beads: Sequence[BEADKEY] = None,
                **kwa) -> Tuple[Set[BEADKEY], Set[BEADKEY]]:
        "returns beads without warnings"
        good: Set[BEADKEY] = set(self.tracks.commonbeads())
        bad : Set[BEADKEY] = (set(self.tracks.availablebeads()) - good)
        cur:  Set[BEADKEY] = (bad | good) if beads is None else set(beads)
        for track in self.tracks.values():
            tmp = (set(track.beads.keys())-bad) & cur
            if tmp:
                bad.update(track.cleaning.bad(tmp,**kwa))
        return bad & cur, (good-bad) & cur

    def messages(self,
                 beads: Sequence[BEADKEY] = None,
                 forceclean               = False,
                 **kwa) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        if beads is None:
            beads = self.tracks.availablebeads()
        return pd.concat([TrackCleaningScript(i).messages(beads, forceclean, **kwa)
                          for i in self.tracks.values()])

    def dataframe(self, beads: Sequence[BEADKEY] = None, **kwa) -> Optional[pd.DataFrame]:
        """
        return a dataframe with all test values
        """
        if beads is None:
            beads = self.tracks.availablebeads()
        return pd.concat([TrackCleaningScript(i).dataframe(beads, **kwa)
                          for i in self.tracks.values()])

    def good(self, **kwa) -> List[BEADKEY]:
        "returns beads without warnings"
        return sorted(self.process(**kwa)[1])

    def bad(self, **kwa) -> List[BEADKEY]:
        "returns beads with warnings"
        return sorted(self.process(**kwa)[0])

    def dropbad(self, **kwa) -> TracksDict:
        "removes bad beads *forever*"
        cpy = self.tracks[...]
        for key, track in cpy.items():
            cpy[key] = TrackCleaningScript(track).dropbad(**kwa)
        return cpy

TracksDict.__doc__ += (
    """
    ## Cleaning

    """+TracksDictCleaningScript.__doc__)
TracksDict.__base__.__doc__ = TracksDict.__doc__ # type: ignore

@addto(TracksDict.__base__)                      # type: ignore
def basedataframe(self,
                  loadall = False,
                  __old__ = TracksDict.basedataframe
                 ) -> pd.DataFrame:
    "Returns a table with some data on the track files"
    frame = __old__(self, loadall)
    if loadall:
        fcn = lambda attr, i: getattr(self[i].cleaning, attr)()
    else:
        fcn = lambda attr, i: (getattr(self[i].cleaning, attr)()
                               if self[i].isloaded else np.NaN)
    return frame.assign(good = frame.key.apply(lambda i: fcn('good', i)),
                        bad  = frame.key.apply(lambda i: fcn('bad',  i)))
__all__ : Tuple[str, ...] = ()
