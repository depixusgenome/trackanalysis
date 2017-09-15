#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track class.

Adds a method for discarding beads with Cleaning warnings
"""
from typing                 import Dict, Optional, Iterator, List, Set, Tuple, cast
from itertools              import product
from utils.decoration       import addto
from data.track             import Track, BEADKEY
from data.tracksdict        import TracksDict
from ..processor            import DataCleaningProcessor, DataCleaningException

class TrackCleaningScript:
    "Adds a method for discarding beads with Cleaning warnings"
    def __init__(self, track: Track) -> None:
        self.track = track

    def process(self, **kwa) -> Dict[BEADKEY, Optional[DataCleaningException.ErrorMessage]]:
        "returns a dictionnary of cleaning results"
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

    def messages(self, **kwa) -> Dict[BEADKEY, str] :
        "returns beads and warnings where applicable"
        return {i: str(j) for i, j in self.process(**kwa).items() if j is not None}

    def dropbad(self, **kwa):
        "removes bad beads *forever*"
        for i in self.bad(**kwa):
            self.track.data.pop(i)

@addto(Track) # type: ignore
@property
def cleaning(self) -> TrackCleaningScript:
    "returns a TrackCleaningScript"
    return TrackCleaningScript(self)

class TracksDictCleaningScript:
    "Adds a method for discarding beads with Cleaning warnings"
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

    def good(self, **kwa) -> List[BEADKEY]:
        "returns beads without warnings"
        return sorted(self.process(**kwa)[1])

    def bad(self, **kwa) -> List[BEADKEY]:
        "returns beads with warnings"
        return sorted(self.process(**kwa)[0])

    def dropbad(self, **kwa):
        "removes bad beads *forever*"
        for bead, track in product(self.bad(**kwa), self.tracks.values()):
            track.data.pop(bead, None)

@addto(TracksDict) # type: ignore
@property
def cleaning(self) -> TracksDictCleaningScript: # pylint: disable=function-redefined
    "returns a TrackCleaningScript"
    return TracksDictCleaningScript(self)

__all__ : Tuple[str, ...] = ()
