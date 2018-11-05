#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds shortcuts for using holoview"
from   typing           import List, Union, Optional, cast
from   dataclasses      import dataclass
import pandas            as     pd
import numpy             as     np

from   data.track        import Track, isellipsis
from   data.views        import Beads
from   .processor        import (RampStatsTask, RampConsensusBeadTask,
                                 RampDataFrameProcessor, RampConsensusBeadProcessor)

@dataclass
class RampAnalysis:
    """
    Analyze ramps
    """
    dataframetask: RampStatsTask     = RampStatsTask()
    consensustask:   RampConsensusBeadTask = RampConsensusBeadTask()
    def __post_init__(self):
        # pylint: disable=not-a-mapping
        if isinstance(self.dataframetask, dict):
            self.dataframetask = RampStatsTask(**cast(dict, self.dataframetask))
        if isinstance(self.consensustask, dict):
            self.consensustask = RampConsensusBeadTask(**cast(dict, self.consensustask))

    def __beads(self,
                track:  Union[Track, Beads],
                beads:  Optional[List[int]] = None,
                status: str                 = None) -> Beads:
        itm = track.beads if isinstance(track, Track) else cast(Beads, track)
        if status is not None and isellipsis(beads):
            beads = self.beads(track, status)
        return itm if isellipsis(beads) else itm[list(cast(list, beads))]

    def beads(self,
              track:    Union[Track, Beads],
              status:   str       = "ok",
              beadlist: Optional[List[int]] = None) -> np.ndarray:
        "return beads which make it through a few filters"
        return (self.dataframe(track, beadlist)
                [lambda x: x.status == status]
                .reset_index()
                .bead.unique())

    def dataframe(self,
                  track:    Union[Track, Beads],
                  beadlist: Optional[List[int]] = None) -> pd.DataFrame:
        """
        return a dataframe containing all info
        """
        beads = self.__beads(track, beadlist)
        return RampDataFrameProcessor.dataframe(beads, **self.dataframetask.config())

    def consensus(self,
                  track:     Union[Track, Beads],
                  beadlist:  Optional[List[int]] = None,
                  normalize: bool                = True) -> pd.DataFrame:
        "return average bead"
        beads = self.__beads(track, beadlist, "ok")
        frame = RampConsensusBeadProcessor.dataframe(beads, **self.consensustask.config())
        proc  = RampConsensusBeadProcessor(task = self.consensustask)
        proc.consensus(frame, normalize)
        return frame
