#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Counts binding events found vs created"
from concurrent.futures         import ProcessPoolExecutor
from copy                       import copy
from typing                     import Dict, List, Tuple
from time                       import clock

import numpy  as np
import pandas as pd

from data                       import Track
from cleaning.processor         import DataCleaningException
from peakfinding.probabilities  import Probability
from peakfinding.processor      import PeakProbabilityProcessor
from peakcalling.tohairpin      import matchpeaks
from taskcontrol.taskcontrol    import create as _create
from taskmodel                  import Task, PHASE
from taskmodel.track            import InMemoryTrackTask
from utils                      import initdefaults
from .bindings                  import ExperimentCreator

class PeakBenchmarkJob:
    "benchmark peaks"
    window:         float                 = 0.005
    experiment:     ExperimentCreator     = ExperimentCreator()
    configurations: Dict[str, List[Task]] = {}
    ntracks:        int                   = 1
    nbeads:         int                   = 1
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def run(self, counts, ntracks = 1, nbeads = 1, nthreads = None):
        "run experiments"
        cpy = copy(self)
        cpy.ntracks = ntracks
        cpy.nbeads  = nbeads

        if nthreads in (1, 0):
            out = [cpy(i) for i in range(counts)]
        else:
            with ProcessPoolExecutor(nthreads) as pool:
                out = list(pool.map(cpy, range(counts)))
        return pd.concat(out)

    @staticmethod
    def __ident(data, name, cnt, val):
        out = np.full(sum(len(i) for i in data['z'][cnt:]), val, dtype = 'i4')
        data[name].append(out)

    def track(self):
        "create a track"
        exp = self.experiment.experiment()
        trk = Track(**exp.track(self.nbeads))
        return exp, trk

    def __call__(self, ident: int):
        data: Dict[str, List[np.ndarray]] = {
            _: [] for _ in (
                'z', 'truez', 'r', 'truer', 't', 'truet', 'config',
                'run', 'track', 'bead', 'delta', 'clock'
            )
        }

        for itrk in range(self.ntracks):
            exp, trk = self.track()
            theo     = [
                np.array(getattr(exp, i)[-2::-1], dtype = 'f4')
                for i in ('positions', 'onrates', 'offrates')
            ]

            ntrk     = len(data['z'])
            for ibd in trk.beads.keys():
                self.__onebead(data, trk, theo, ibd)

            self.__ident(data, 'track', ntrk, itrk)

        self.__ident(data, 'run', 0, ident)
        return pd.DataFrame({i: np.concatenate(j) for i, j in data.items()})

    def __onebead(self, data, trk, theo, ibd):
        cnt = len(data['z'])
        for name, tasks in self.configurations.items():
            dur             = clock()
            ids, pks, probs = self.__run(theo[0], trk, tasks, ibd)
            dur             = clock()-dur
            self.__copy(data, ids, "z", pks,                                  theo[0])
            self.__copy(data, ids, "t", [i.averageduration for i in probs],   theo[1])
            self.__copy(data, ids, "r", [i.hybridisationrate for i in probs], theo[2])
            self.__deltas(data, pks, ids, theo[0])

            data['clock'].append(np.full(sum(len(i) for i in data['z'][-2:]), dur))
            data['config'].append(np.full(sum(len(i) for i in data['z'][-2:]), name))
        self.__ident(data, 'bead', cnt, ibd)

    @staticmethod
    def __deltas(data, pks, ids, theo):
        deltas        = np.full((len(pks), 3), 1e6, dtype = 'f4')
        deltas[:,1]   = pks
        tmp           = ids > 0
        deltas[tmp,0] = theo[ids[tmp]-1]
        tmp           = (ids >= 0) & (ids < (len(theo)-1))
        deltas[tmp,2] = theo[ids[tmp]+1]
        deltas        = np.nanmin(np.abs(np.diff(deltas, axis = 1)), axis = 1)
        deltas[deltas > 1e5]   = np.NaN
        deltas[deltas <= 1e-5] = np.NaN
        data['delta'].append(deltas)
        data['delta'].append(np.full(len(data['z'][-1]), np.NaN, dtype = 'f4'))

    @staticmethod
    def __copy(data, ids, name, exp, true):
        good       = ids >= 0
        itms       = np.full(len(exp), np.NaN, dtype = 'f4')
        itms[good] = true[ids[good]]

        data[name].append(exp)
        data[name].append(np.full(len(true)-good.sum(), np.NaN, dtype = 'f4'))

        data['true'+name].append(itms)
        data['true'+name].append(true[np.setdiff1d(np.arange(len(true)), ids)])

    def __run(self, theo, trk, tasks, ibd) -> Tuple[np.ndarray, np.ndarray, List[Probability]]:
        try:
            cur = next(_create(InMemoryTrackTask(track = trk), *tasks).run())[ibd]
        except DataCleaningException:
            return np.empty(0, dtype = 'i4'), np.empty(0, dtype = 'f4'), []

        prob = Probability(
            minduration = PeakProbabilityProcessor.extractminduration(tasks),
            framerate   = trk.framerate
        )
        ends  = trk.phase.duration(..., PHASE.measure)
        pks   = cur['peaks'] - cur['peaks'][0]
        return (
            matchpeaks(theo, pks, self.window),
            pks,
            [prob(i, ends) for i in cur['events']]
        )
