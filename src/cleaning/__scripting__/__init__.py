#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=function-redefined
"""
Monkey patches the Track class.

Adds a method for discarding beads with Cleaning warnings
"""
from   typing                       import (Dict, Optional, Iterator, List, Any,
                                            Set, Union, Tuple, Sequence, cast)
from   itertools                        import product
import numpy                            as     np
import pandas                           as     pd
from   utils.decoration                 import addproperty, addto
from   control.processor.dataframe      import DataFrameFactory
from   model.__scripting__              import Tasks
from   model.__scripting__.track        import LocalTasks
from   data.views                       import BEADKEY
from   data.track                       import dropbeads
from   data.__scripting__.track         import Track
from   data.__scripting__.tracksdict    import TracksDict
from   ..processor                      import (DataCleaningProcessor,
                                                DataCleaningErrorMessage)
from   ..beadsubtraction                import BeadSubtractionTask

@addto(BeadSubtractionTask, staticmethod)
def __scripting_save__() -> bool:
    return False

class BeadSubtractionDescriptor:
    "A descriptor for adding subtracted beads"
    NAME    = Tasks(BeadSubtractionTask).value
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
        else:
            inst.tasks[self.NAME] = BeadSubtractionTask(beads = list(lst))

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
    """
    def __init__(self, track: Track) -> None:
        self.track = track

    def process(self,
                beads: Sequence[BEADKEY] = None,
                **kwa) -> Dict[BEADKEY, Optional[DataCleaningErrorMessage]]:
        "returns a dictionnary of cleaning results"
        itms = self.track.beadsonly[list(beads)] if beads else self.track.beadsonly
        get  = lambda x: x if x is None else x.args[0]
        return {info[0]: get(DataCleaningProcessor.compute(itms, info, **kwa))
                for info in cast(Iterator, itms)}

    def good(self, beads: Sequence[BEADKEY] = None, **kwa) -> List[BEADKEY]:
        "returns beads without warnings"
        return [i for i, j in self.process(beads, **kwa).items() if j is None]

    def bad(self, beads: Sequence[BEADKEY] = None, **kwa) -> List[BEADKEY]:
        "returns beads with warnings"
        return [i for i, j in self.process(beads, **kwa).items() if j is not None]

    def messages(self,
                 beads: Sequence[BEADKEY] = None,
                 forceclean                  = False,
                 **kwa) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        ids   = [] # type: List[int]
        types = [] # type: List[str]
        cycs  = [] # type: List[int]
        msgs  = [] # type: List[str]

        if forceclean or self.track.cleaned is False: # type: ignore
            for i, j in self.process(**kwa).items():
                if j is None:
                    continue
                itms = j.data()

                cycs .extend([i[0] for i in itms])
                types.extend([i[1] for i in itms])
                msgs .extend([i[2] for i in itms])
                ids.extend((cast(int, i),)*(len(msgs)-len(ids)))

        miss = list(set(beads)-set(self.track.beadsonly.keys())) if beads else []
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

    def dropbad(self, **kwa) -> Track:
        "removes bad beads *forever*"
        return dropbeads(self.track, *self.bad(**kwa)) # type: ignore

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
        kwa['beads'] = beads
        bad  = set() # type: Set[BEADKEY]
        allb = set() # type: Set[BEADKEY]
        fcn  = DataCleaningProcessor.compute
        for track in self.tracks.values():
            frame  = track.beadsonly
            cur    = set(frame.keys())-bad
            allb.update(cur)
            bad.update({i[0] for i in frame[list(cur)] if fcn(frame, i, **kwa) is None})
        return bad, allb-bad

    def messages(self,
                 beads: Sequence[BEADKEY] = None,
                 forceclean               = False,
                 **kwa) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        if beads is None:
            beads = self.tracks.availablebeads()
        return pd.concat([TrackCleaningScript(i).messages(beads, forceclean, **kwa)
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
