#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating PeaksDict for scripting purposes"
import sys
from   typing       import List
from   copy         import deepcopy, copy as shallowcopy
import numpy        as np
import pandas       as pd
from   utils.decoration import addto
from   .processor       import PeaksDict, FitToHairpinDict

assert 'scripting' in sys.modules

@addto(FitToHairpinDict)
def dataframe(self, conversion = 'best') -> pd.DataFrame:
    "converts to a pandas dataframe"
    def _cnv(info):
        cnt   = 0
        items = [[], [], [], [], [], []]
        res   = info[1]
        for (peak, evts), dna in zip(PeaksDict.measure(deepcopy(res.events)),
                                     res.peaks):
            vals = [i for i in enumerate(evts) if i[1] is not None]
            dna  = dna[1] if dna[1] >= 0 else np.NaN

            items[2].append([i for i, _ in vals])
            items[3].append(np.full(len(vals), peak, dtype = 'f4'))
            items[4].append(np.full(len(vals), dna,  dtype = 'f4'))
            items[5].append([i for _, i in vals])
            cnt += len(vals)


        key = min(res.distances, key = lambda x: res.distances[x].value)
        items[0].append(np.full(cnt, key))
        items[1].append(np.full(cnt, info[0]))

        names = ('hpin', 'bead', 'cycle', 'peak', 'dnapeak', 'event')
        data  = pd.DataFrame(dict(zip(names, (np.concatenate(i) for i in items))))

        dist  = res.distances[key if conversion == 'best' else conversion]
        data.insert(4, 'dnaevent', (data.event-dist.bias)*dist.stretch)
        data.insert(4, 'distance', data.dnaevent-data.dnapeak)
        return info[0], data
    return pd.concat([i for _, i in shallowcopy(self).withaction(_cnv)])

__all__: List[str] = []
