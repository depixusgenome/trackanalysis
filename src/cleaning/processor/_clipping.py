#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all cleaning related tasks"
from   functools                import partial
from   typing                   import Optional
import numpy                    as     np
from   data                     import Track
from   taskmodel                import Level, PHASE, Task
from   taskcontrol.processor    import Processor
from   utils                    import initdefaults
from   ._datacleaning           import DataCleaningErrorMessage, DataCleaningException
from   ..datacleaning           import Partial

class ClippingTask(Task):
    "Task discarding phase 5 data below phase 1 or above phase 3"
    level         = Level.bead
    lowfactor     = 4.
    highfactor    = 0.
    low           = PHASE.initial
    high          = PHASE.pull
    correction    = PHASE.measure
    replacement   = np.NaN
    minpopulation = 80.

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self, **kwa)

    def minthreshold(self, track:Track, key:int, data: np.ndarray) -> Optional[float]:
        "return the min threshold"
        if self.lowfactor is None or self.lowfactor <= 0.:
            return None
        hfs = track.rawprecision(key)
        out = track.phaseposition(self.low,  data)-hfs*self.lowfactor
        return out if np.isfinite(out) else None

    def maxthreshold(self, track:Track, key:int, data: np.ndarray) -> Optional[float]:
        "return the min threshold"
        if self.highfactor is None:
            return None
        hfs = track.rawprecision(key)
        out = track.phaseposition(self.high, data)+hfs*self.highfactor
        return out if np.isfinite(out) else None

    def __call__(self, track:Track, key:int, data: np.ndarray):
        maxv = self.maxthreshold(track, key, data)
        minv = self.minthreshold(track, key, data)
        if minv is None and maxv is None:
            return

        pha  = track.phase.select(..., [self.correction, self.correction+1]).ravel()
        itms = np.split(data, pha)[1::2]
        if minv is None and maxv is not None:
            for i in itms:
                i[~np.isfinite(i)] = maxv+1
                i[(i > maxv)]      = self.replacement

        elif maxv is None and minv is not None:
            for i in itms:
                i[~np.isfinite(i)] = minv-1
                i[(i < minv)]      = self.replacement

        elif maxv is not None and minv is not None:
            for i in itms:
                i[~np.isfinite(i)]         = maxv+1
                i[(i < minv) | (i > maxv)] = self.replacement

    def partial(self, track:Track, key:int, data: np.ndarray) -> Optional[Partial]:
        "Create an output similar to ones from DataCleaningTask"
        maxv = self.maxthreshold(track, key, data)
        minv = self.minthreshold(track, key, data)
        if minv is None and maxv is None:
            return None

        pha    = track.phase.select(..., [self.correction, self.correction+1]).ravel()
        itms   = [(i[np.isfinite(i)], len(i)) for i in np.split(data, pha)[1::2]]

        maxarr = (
            np.array([(i>maxv).sum() for i, _ in itms], dtype = 'i4')  if maxv is not None else
            np.zeros(len(itms), dtype = 'i4')
        )
        minarr = (
            np.array([(i<minv).sum() for i, _ in itms], dtype = 'i4')  if minv is not None else
            np.zeros(len(itms), dtype = 'i4')
        )
        sizes = np.array([i for _, i in itms], dtype = 'i4')
        return Partial(
            "clipping",
            np.empty(0, dtype = 'i4'),
            np.empty(0, dtype = 'i4'),
            (minarr + maxarr) / sizes
        )

class ClippingErrorMessage(DataCleaningErrorMessage):
    "a clipping exception message"
    def getmessage(self, percentage = False):
        "returns the message"
        data = self.data()[0][-1][1:].strip()
        return 'has less than %s %% points with the range of phases 1 and 3' % data

    def data(self):
        "returns a message if the test is invalid"
        pop  = self.config.get('minpopulation', self.tasktype().minpopulation)
        return [(None, 'clipping', '< %d' % pop)]

class ClippingExeption(DataCleaningException):
    "a clipping exception"

class ClippingProcessor(Processor[ClippingTask]):
    "Processor for cleaning the data"
    @classmethod
    def _action(cls, task, frame, info):
        "action of clipping"
        task(frame.track, *info)
        if task.minpopulation > 0.:
            exc = cls.test(task, frame, info)
            if isinstance(exc, Exception):
                raise exc # pylint: disable=raising-bad-type
        return info

    @staticmethod
    def test(task, frame, info)-> Optional[ClippingExeption]:
        "test how much remaining pop"
        if np.isfinite(info[1]).sum() <= len(info[1]) * task.minpopulation * 1e-2:
            ncy = getattr(frame.track, 'ncycles', 0)
            msg = ClippingErrorMessage(
                None, task.config(), type(task), info[0], frame.parents, ncy
            )
            return ClippingExeption(msg, 'warning')
        return None

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        if toframe is None:
            return partial(cls.apply, **cnf)
        return toframe.withaction(partial(cls._action, ClippingTask(**cnf)))

    def run(self, args):
        "updates the frames"
        return args.apply(partial(self.apply, **self.config()))
