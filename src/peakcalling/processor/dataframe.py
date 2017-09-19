#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing                      import Dict, List, cast # pylint: disable=unused-import
from   copy                        import deepcopy
import numpy  as np
from   control.processor.dataframe import DataFrameFactory
from   peakfinding.data            import PeaksDict, PeaksArray
from   .fittohairpin               import FitToHairpinDict, FitBead

class FitsDataFrameFactory(DataFrameFactory):
    """
    converts to a pandas dataframe.
    """
    FRAME_TYPE = FitToHairpinDict
    # pylint: disable=arguments-differ
    def _run(self, _1, _2, res:FitBead) -> Dict[str, np.ndarray]:
        out = {i: [] for i in ('cycle', 'peak', 'event')} # type: Dict[str, List[np.ndarray]]
        out.update({i: [] for i in res.distances})
        for (peak, evts) in PeaksDict.measure(cast(PeaksArray, deepcopy(res.events))):
            vals = [i for i in enumerate(evts) if i[1] is not None]

            out['cycle'].append(np.array([i for i, _ in vals]))
            out['peak'].append(np.full(len(vals), peak, dtype = 'f4'))
            out['event'].append(np.array([i for _, i in vals]))
            for i, j in res.distances.items():
                out[i].append((out['event'][-1]-j.bias)*j.stretch)
        return {i: np.concatenate(j) for i, j in out.items()}
