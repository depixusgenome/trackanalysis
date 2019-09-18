#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds shortcuts for using holoview"
from   typing           import List, Union, Optional, Any, Dict, cast
import pandas            as     pd
import numpy             as     np

from   utils             import initdefaults
from   data.track        import Track, isellipsis
from   data.views        import Beads
from   taskmodel.__scripting__  import Tasks
from   ..processor              import (
    RampConsensusBeadTask, RampDataFrameProcessor, RampConsensusBeadProcessor,
    RampStatsTask
)

assert not hasattr(Tasks, '_default_dataframe')

def _default_dataframe(self, *resets, measures = None, **kwa):
    # pylint: disable=protected-access
    ramp = (
        kwa.pop('ramp', kwa.pop('ramps', False))
        or measures and measures.pop('ramp', measures.pop('ramps', False))
    )
    if ramp:
        kwa['current'] = RampStatsTask(**dict(kwa, **(measures if measures else {})))
    return self._default_call(*resets, **kwa)

setattr(Tasks, '_default_dataframe', _default_dataframe)

class RampAnalysis:
    """
    Analyze ramps
    """
    cleaning:      Dict[str, float] = dict(
        minextent     = 0.,
        maxextent     = 10.,
        maxsaturation = 100.
    )
    dataframetask: Dict[str, Any]   = {}
    consensustask: Dict[str, Any]   = {}

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def beadsview(self, track: Union[Track, Beads], *tasks) -> Beads:
        "return the beads view"
        return (
            track.apply(
                Tasks.cleaning (**self.cleaning, instrument = track.instrument['type']),
                Tasks.alignment(**self.cleaning, instrument = track.instrument['type']),
                *tasks,
            ) if isinstance(track, Track) else
            cast(Beads, track)
        )

    def beads(
            self,
            track:    Union[Track, Beads],
            status:   str       = "ok",
            beadlist: Optional[List[int]] = None,
            **kwa
    ) -> np.ndarray:
        "return beads which make it through a few filters"
        return (
            self.dataframe(track, beadlist, **kwa)
            [lambda x: x.status == status]
            .reset_index()
            .bead.unique()
        )

    def dataframe(
            self,
            track:    Union[Track, Beads],
            beadlist: Optional[List[int]] = None,
            **kwa
    ) -> pd.DataFrame:
        """
        return a dataframe containing all info
        """
        beads  = self.__beads(track, beadlist)
        dframe = RampDataFrameProcessor.dataframe(
            beads,
            **dict(self.dataframetask, **kwa)
        )
        dframe.__dict__['tasklist'] = [
            Tasks.trackreader(path = track.path),
            Tasks.cleaning(**self.cleaning, instrument = track.instrument['type']),
            Tasks.alignment(**self.cleaning, instrument = track.instrument['type']),
            RampStatsTask(**dict(self.dataframetask, **kwa))
        ]
        return dframe

    def consensus(
            self,
            track:     Union[Track, Beads],
            beadlist:  Optional[List[int]] = None,
            **kwa
    ) -> pd.DataFrame:
        "return average bead"
        beads = self.__beads(track, beadlist, "ok")
        task  = RampConsensusBeadTask(**dict(self.consensustask, **kwa))
        frame = RampConsensusBeadProcessor.dataframe(beads, **task.config())
        proc  = RampConsensusBeadProcessor(task = task)
        proc.consensus(frame, task.normalize)
        return frame

    def __beads(self,
                track:  Union[Track, Beads],
                beads:  Optional[List[int]] = None,
                status: str                 = None) -> Beads:
        itm = self.beadsview(track)
        if status is not None and isellipsis(beads):
            beads = self.beads(track, status)
        return itm if isellipsis(beads) else itm[list(cast(list, beads))]


__all__ = ['RampAnalysis']
