#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=function-redefined
"""
Monkey patches the Track class.

Adds a method for discarding beads with Cleaning warnings
"""
from   typing                       import (Dict, Optional, Iterator, List,
                                            Set, Tuple, cast)
from   itertools                        import product
import numpy                            as     np
import pandas                           as     pd
from   utils.decoration                 import addproperty
from   control.processor.dataframe      import DataFrameFactory
from   data.views                       import BEADKEY
from   data.track                       import dropbeads
from   data.__scripting__.track         import Track
from   data.__scripting__.tracksdict    import TracksDict
from   ..processor                      import (DataCleaningProcessor,
                                                DataCleaningException)

@addproperty(Track.__base__, 'cleaning')
class TrackCleaningScript:
    """
    Provides methods for finding beads with cleaning warnings and possibly discarding them.

    One can do:

    * `track.cleaning.good()`: lists good beads
    * `track.cleaning.bad()`: lists bad beads
    * `track.cleaning.messages()`: lists all messages
    * `track.cleaning.dropbad`: returns a track with only good beads loaded.
    """
    def __init__(self, track: Track) -> None:
        self.track = track

    def process(self, **kwa) -> Dict[BEADKEY, Optional[DataCleaningException.ErrorMessage]]:
        "returns a dictionnary of cleaning results"
        if 'beads' in kwa:
            beads = self.track.beadsonly[list(kwa.pop('beads'))]
        else:
            beads = self.track.beadsonly
        get   = lambda x: x if x is None else x.args[0]
        return {info[0]: get(DataCleaningProcessor.compute(beads, info, **kwa))
                for info in cast(Iterator, beads)}

    def good(self, **kwa) -> List[BEADKEY]:
        "returns beads without warnings"
        return [i for i, j in self.process(**kwa).items() if j is None]

    def bad(self, **kwa) -> List[BEADKEY]:
        "returns beads with warnings"
        return [i for i, j in self.process(**kwa).items() if j is not None]

    def messages(self, **kwa) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        beads = [] # type: List[int]
        types = [] # type: List[str]
        cycs  = [] # type: List[int]
        msgs  = [] # type: List[str]
        for i, j in self.process(**kwa).items():
            if j is None:
                continue
            itms = j.data()

            cycs .extend([i[0] for i in itms])
            types.extend([i[1] for i in itms])
            msgs .extend([i[2] for i in itms])
            beads.extend((cast(int, i),)*(len(msgs)-len(beads)))

        name = DataFrameFactory.trackname(self.track)
        return pd.DataFrame(dict(track   = np.full(len(beads), name),
                                 bead    = beads,
                                 cycles  = cycs,
                                 types   = types,
                                 message = msgs))

    def dropbad(self, **kwa) -> Track:
        "removes bad beads *forever*"
        return dropbeads(self.track, *self.bad(**kwa)) # type: ignore

Track.__doc__ += (
    """
    * *cleaning* """+TrackCleaningScript.__doc__.split('\n')[1].strip())
Track.__base__.__doc__ = Track.__doc__

@addproperty(TracksDict.__base__, 'cleaning')
class TracksDictCleaningScript:
    """
    Adds means for finding beads with cleaning warnings and possibly discarding them.

    One can do:

    * `tracks.cleaning.good()`: lists beads which are good throughout all tracks
    * `tracks.cleaning.bad()`: lists beads bad at least in one track
    * `tracks.cleaning.messages()`: lists all messages
    * `tracks.cleaning.dropbad`: returns a *TracksDict* with tracks with only
    good beads loaded.
    """
    def __init__(self, tracks: TracksDict) -> None:
        self.tracks = tracks

    def process(self, **kwa) -> Tuple[Set[BEADKEY], Set[BEADKEY]]:
        "returns beads without warnings"
        bad   = set() # type: Set[BEADKEY]
        beads = set() # type: Set[BEADKEY]
        fcn   = DataCleaningProcessor.compute
        for track in self.tracks.values():
            frame  = track.beadsonly
            cur    = set(frame.keys())-bad
            beads |= cur
            bad   |= {i[0] for i in frame[list(cur)] if fcn(frame, i, **kwa) is None}
        return bad, beads-bad

    def messages(self, **kwa) -> pd.DataFrame:
        "returns beads and warnings where applicable"
        return pd.concat([TrackCleaningScript(i).messages(**kwa)
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
TracksDict.__base__.__doc__ = TracksDict.__doc__
__all__ : Tuple[str, ...] = ()
