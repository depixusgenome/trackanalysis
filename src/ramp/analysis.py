#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds shortcuts for using holoview"
from   typing           import List, Union, Optional, cast
from   dataclasses      import dataclass
import pandas            as     pd
import numpy             as     np

from   data.track        import Track, isellipsis
from   data.views        import Beads
from   .processor        import (RampDataFrameTask, RampAverageZTask,
                                 RampDataFrameProcessor, RampAverageZProcessor)

@dataclass
class RampAnalysis:
    """
    Analyze ramps
    """
    dataframetask: RampDataFrameTask          = RampDataFrameTask()
    averagetask:   RampAverageZTask           = RampAverageZTask()
    def __post_init__(self):
        # pylint: disable=not-a-mapping
        if isinstance(self.dataframetask, dict):
            self.dataframetask = RampDataFrameTask(**cast(dict, self.dataframetask))
        if isinstance(self.averagetask, dict):
            self.averagetask = RampAverageZTask(**cast(dict, self.averagetask))

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

    def average(self,
                track:    Union[Track, Beads],
                beadlist: Optional[List[int]] = None) -> pd.DataFrame:
        "return average bead"
        beads = self.__beads(track, beadlist, "ok")
        frame = RampAverageZProcessor.dataframe(beads, **self.averagetask.config())
        self.averagetask.consensus(frame)
        return frame
