#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
from   typing                   import  Optional, Dict, Tuple, cast

import numpy                    as     np

from cleaning.view              import DataCleaningModelAccess
from peakcalling.tohairpin      import Distance
from tasksequences.modelaccess  import SequencePlotModelAccess
from tasksequences              import splitoligos
from utils                      import NoArgs

from .._peakinfo                import PeakInfoModelAccess
from ._processors               import runbead
from ._jobs                     import JobRunner
from ._plotmodel                import PeaksPlotModel
from ._taskaccess               import (
    EventDetectionTaskAccess, PeakSelectorTaskAccess, SingleStrandTaskAccess,
    BaselinePeakFilterTaskAccess, FitToReferenceAccess, FitToHairpinAccess
)

# pylint: disable=unused-import,wrong-import-order,ungrouped-imports
from peakfinding.processor.__config__    import PeakSelectorTask

# pylint: disable=too-many-instance-attributes
class PeaksPlotModelAccess(SequencePlotModelAccess, DataCleaningModelAccess):
    "Access to peaks"
    def __init__(self):
        DataCleaningModelAccess.__init__(self)
        SequencePlotModelAccess.__init__(self)

        self.eventdetection = EventDetectionTaskAccess(self)
        self.peakselection  = PeakSelectorTaskAccess(self)
        self.singlestrand   = SingleStrandTaskAccess(self)
        self.baselinefilter = BaselinePeakFilterTaskAccess(self)
        self.fittoreference = FitToReferenceAccess(self)
        self.identification = FitToHairpinAccess(self)
        self.peaksmodel     = PeaksPlotModel()
        self.pool           = JobRunner(self)

    def swapmodels(self, ctrl) -> bool:
        "swap models with those in the controller"
        if super().swapmodels(ctrl):
            ctrl.display.update(
                self.peaksmodel.display, peaks = PeakInfoModelAccess(self).createpeaks([])
            )
            return True
        return False

    def observe(self, ctrl):
        "add to the controller"
        super().observe(ctrl)

        self.pool.observe(ctrl)

        @ctrl.theme.observe(self._tasksconfig)
        @ctrl.display.observe(self._tasksdisplay)
        @ctrl.theme.hashwith(self._tasksdisplay)
        def _ontasks(old, **_):
            if 'rescaling' not in old and "taskcache" not in old:
                return

            root  = self._tasksdisplay.roottask
            if root is None:
                return

            model = self._tasksconfig
            instr = self.instrument
            coeff = float(model.rescaling[instr]) if instr in model.rescaling else 1.
            if abs(coeff - self.peaksmodel.config.rescaling) < 1e-5:
                return

            cur    = coeff
            coeff /= self.peaksmodel.config.rescaling
            ctrl.theme.update(
                self.peaksmodel.config,
                rescaling         = cur,
                estimatedstretch  = self.peaksmodel.config.estimatedstretch/coeff
            )

            self.identification.rescale(ctrl, self, coeff)

        @ctrl.tasks.observe
        @ctrl.tasks.hashwith(self._tasksdisplay)
        def _onopeningtracks(controller, models, **_):
            "tries to add a FitToHairpinTask if sequences & oligos are available"
            if not self.sequences(...):
                return

            path = self.sequencepath
            cls  = self.identification.tasktype
            for isarchive, proc in models:
                model = proc.model
                if isarchive or not model or not getattr(model[0], 'path', None):
                    continue

                ols = splitoligos("kmer", path = model[0].path)
                if not ols:
                    continue
                proc.add(
                    cls(sequence = path, oligos = ols),
                    controller.processortype(cls),
                    index = self._tasksconfig.defaulttaskindex(proc.model, cls)
                )

    def getfitparameters(self, key = NoArgs, bead = NoArgs) -> Tuple[float, float]:
        "return the stretch  & bias for the current bead"
        if bead is not NoArgs:
            tmp   = None if self.roottask is None else self._tasksdisplay.cache(-1)()
            cache = (None, None) if tmp is None or bead not in tmp else tmp[bead]

        if key is not None:
            if bead is NoArgs:
                dist = self.peaksmodel.display.distances
            else:
                dist = getattr(cache[0], "distances", {})

            key  = self.sequencekey if key is NoArgs else key
            if key in dist:
                return dist[key][1:]

        out = self.identification.constraints()[1:]
        if out[0] is None:
            out = self.peaksmodel.config.estimatedstretch, out[1]
        if out[1] is None:
            out = out[0], self.peaksmodel.display.estimatedbias
            if bead is not NoArgs:
                if not isinstance(cache, Exception):
                    out = out[0], getattr(cache[1], "peaks", [0])[0]
        return cast(Tuple[float, float], out)

    @property
    def stretch(self) -> float:
        "return the stretch for the current bead"
        return self.getfitparameters()[0]

    @property
    def bias(self) -> float:
        "return the bias for the current bead"
        return self.getfitparameters()[1]

    @property
    def sequencekey(self) -> Optional[str]:
        "returns the sequence key"
        dist = self.peaksmodel.display.distances
        tmp  = min(dist, key = dist.__getitem__) if dist else None
        return self.sequencemodel.display.hpins.get(self.sequencemodel.tasks.bead,
                                                    tmp)

    @sequencekey.setter
    def sequencekey(self, value):
        "sets the new sequence key"
        self.setnewsequencekey(value)

    @property
    def constraintspath(self):
        "return the path to constraints"
        return self.peaksmodel.display.constraintspath.get(self.roottask, None)

    @property
    def useparams(self):
        "return the path to constraints"
        return self.peaksmodel.display.useparams

    @property
    def distances(self) -> Dict[str, Distance]:
        "return the computed distances"
        return self.peaksmodel.display.distances

    @property
    def peaks(self) -> Dict[str, np.ndarray]:
        "return the computed peaks"
        return self.peaksmodel.display.peaks

    @property
    def defaultidenfication(self):
        "returns the default identification task"
        return self.identification.default(self)

    def runbead(self):
        "runs the bead"
        pksel    = cast(PeakSelectorTask, self.peakselection.task)
        pkinfo   = PeakInfoModelAccess(self)
        out      = runbead(self.processors(), self.bead, self.fittoreference.refcache)
        tmp, dtl = out if isinstance(out, tuple) else (None, None)  # type: ignore
        data     = tuple(() if pksel is None else pksel.details2output(dtl))

        self._updatedisplay(
            self.peaksmodel.display,
            distances     = getattr(tmp, 'distances', {}),
            estimatedbias = getattr(dtl, 'peaks', [0.])[0],
            baseline      = self.baselinefilter.compute(tmp, data),
            singlestrand  = self.singlestrand.compute(tmp, data),
        )

        # pkinfo.createpeaks requires the distances to be already set!
        self._updatedisplay(
            self.peaksmodel.display,
            peaks = pkinfo.createpeaks(data),
        )

        if dtl is not None:
            self.setnewsequencekey(self.sequencekey)

        if isinstance(out, Exception):
            raise out  # pylint: disable=raising-bad-type
        return dtl

    def reset(self) -> bool:  # type: ignore
        "adds tasks if needed"
        if self.rawtrack is None:
            return True

        if self.eventdetection.task is None:
            self.eventdetection.update()

        if self.peakselection.task is None:
            self.peakselection.update()

        self.fittoreference.resetmodel()
        self.identification.resetmodel(self)
        self.singlestrand.resetmodel(self)
        return False

    def fiterror(self) -> bool:
        "True if not fit was possible"
        if self.identification.task is None:
            return False
        maxv = np.finfo('f4').max
        dist = self.peaksmodel.display.distances
        return all(i[0] == maxv or not np.isfinite(i[0]) for i in dist.values())
