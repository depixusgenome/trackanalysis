#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=function-redefined
"""
Monkey patches the Track class.

Adds a method for discarding beads with Cleaning warnings
"""
from   typing                       import (Dict, Optional, Iterator, List,
                                            Set, Tuple, Sequence, cast)
from   itertools                        import product
import numpy                            as     np
import pandas                           as     pd
from   utils.decoration                 import addproperty, addto
from   control.processor.dataframe      import DataFrameFactory
from   data.views                       import BEADKEY
from   data.track                       import dropbeads
from   data.__scripting__.track         import Track
from   data.__scripting__.tracksdict    import TracksDict
from   ..processor                      import (DataCleaningProcessor,
                                                DataCleaningException)
from   ..beadsubtraction                import BeadSubtractionTask

@addto(BeadSubtractionTask)
def __scripting_save__(self):
    self.beads.clear()

@addproperty(Track.__base__, 'cleaning')
class TrackCleaningScript:
    """
    Provides methods for finding beads with cleaning warnings and possibly discarding them.

    One can do:

    * `track.cleaning.good()`: lists good beads
    * `track.cleaning.bad()`: lists bad beads
    * `track.cleaning.messages()`: lists all messages
    * `track.cleaning.dropbad()`: returns a track with only good beads loaded.
    """
    def __init__(self, track: Track) -> None:
        self.track = track

    def process(self,
                beads: Sequence[BEADKEY] = None,
                **kwa) -> Dict[BEADKEY, Optional[DataCleaningException.ErrorMessage]]:
        "returns a dictionnary of cleaning results"
        if beads:
            itms = self.track.beadsonly[list(beads)]
        else:
            itms = self.track.beadsonly
        get = lambda x: x if x is None else x.args[0]
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

        if forceclean or self.track.cleaned is False:
            for i, j in self.process(**kwa).items():
                if j is None:
                    continue
                itms = j.data()

                cycs .extend([i[0] for i in itms])
                types.extend([i[1] for i in itms])
                msgs .extend([i[2] for i in itms])
                ids.extend((cast(int, i),)*(len(msgs)-len(ids)))

        miss = list(set(beads)-set(self.track.beadsonly.keys()))
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
    * `cleaning` """+TrackCleaningScript.__doc__.split('\n')[1].strip())
Track.__base__.__doc__ = Track.__doc__ # type: ignore

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
    # Cleaning

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
