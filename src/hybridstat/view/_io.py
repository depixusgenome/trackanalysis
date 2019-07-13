#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"IO for peaksplot"
from typing                               import Optional, Tuple, Union, List
from pathlib                              import Path
from copy                                 import deepcopy
from concurrent.futures                   import ProcessPoolExecutor, ThreadPoolExecutor

from eventdetection.processor             import ExtremumAlignmentTask
from cleaning.processor                   import (
    DataCleaningTask, DataCleaningException, ClippingTask
)
from peakfinding.processor                import PeakSelectorTask
from peakfinding.reporting.processor      import PeakFindingExcelTask
from peakcalling.processor                import FitToHairpinTask, BeadsByHairpinTask
from peakcalling.processor.fittoreference import (FitToReferenceTask, FitToReferenceDict,
                                                  TaskViewProcessor, BEADKEY)
from taskcontrol.processor.utils          import ExceptionCatchingTask
from taskcontrol.taskcontrol              import create as _createdata
from taskcontrol.taskio                   import (
    ConfigTrackIO, ConfigGrFilesIO, ConfigMuWellsFilesIO, TaskIO
)
from utils.logconfig                      import getLogger
from utils.gui                            import startfile
from view.base                            import spawn, threadmethod
from view.dialog                          import FileDialogTheme

from ..reporting.processor                import HybridstatExcelTask
from ._model                              import PeaksPlotModelAccess

LOGS = getLogger(__name__)

class _PeaksIOMixin:
    def __init__(self, ctrl):
        type(self).__bases__ [1].__init__(self, ctrl) # type: ignore
        self.__ctrl = ctrl

    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        "opens a track file and adds a alignment"
        # pylint: disable=no-member
        items = type(self).__bases__[1].open(self, path, model) # type: ignore

        if items is not None:
            task = PeaksPlotModelAccess(self.__ctrl, True).defaultidenfication
            if task is not None:
                items[0] += (task,)
        return items

class PeaksConfigTrackIO(_PeaksIOMixin, ConfigTrackIO): # type: ignore
    "selects the default tasks"

class PeaksConfigMuWellsFilesIO(_PeaksIOMixin, ConfigMuWellsFilesIO): # type: ignore
    "selects the default tasks"

class PeaksConfigGRFilesIO(_PeaksIOMixin, ConfigGrFilesIO): # type: ignore
    "selects the default tasks"

class _SafeTask(FitToReferenceTask):
    "safe fit to ref"

class _SafeDict(FitToReferenceDict): # pylint: disable=too-many-ancestors
    "iterator over peaks grouped by beads"
    def _getrefdata(self, key):
        try:
            out = super()._getrefdata(key)
        except DataCleaningException:
            out = True
        return out

class _SafeProc( # pylint: disable=duplicate-bases
        TaskViewProcessor[_SafeTask, _SafeDict, BEADKEY]
):
    "Changes the Z axis to fit the reference"

FileDialogTheme.types['pkz'] = (u'pickled report', '.pkz')
class ConfigXlsxIOTheme:
    "ConfigXlsxIOTheme"
    name   = 'hybridstat.configxlsxio'
    start  = ('Report in progress ...', 'normal')
    end    = ('The report has been created', 'normal')
    errors = {'running': ("Can only create one report at a time", "warning")}

class ConfigXlsxIO(TaskIO):
    "Ana IO saving only the current project"
    EXT      = 'xlsx', 'csv', 'pkz'
    RUNNING  = False
    POOLTYPE = ProcessPoolExecutor
    def __init__(self, ctrl):
        super().__init__(ctrl)
        self.__ctrl  = ctrl
        self.__theme = ctrl.theme.add(ConfigXlsxIOTheme(), True)

    def save(self, path:str, models):
        "creates a Hybridstat report"
        pksmdl = PeaksPlotModelAccess(self.__ctrl, True)
        curr   = pksmdl.roottask
        models = [i for i in models if curr is i[0]]
        if not len(models):
            raise IOError("Nothing to save", "warning")

        def _end(exc):
            if exc is None and not Path(path).exists():
                exc = IOError("Report file created but not not found!")

            if isinstance(exc, IOError) and len(exc.args) == 1:
                if len(exc.args) == 1:
                    msg = self.__theme.errors.get(exc.args[0], None)
                    if msg is not None:
                        self.__msg(msg)
                        LOGS.debug('Failed report creation with %s', msg[0])
                        return
            if exc is not None:
                LOGS.exception(exc)
                self.__msg(exc)
            else:
                exc = self.__theme.end
                self.__msg(exc)
                startfile(path)

        model = self.__complete_model(list(models[0]), pksmdl)
        try:
            LOGS.info('%s saving %s', type(self).__name__, path)
            ret = self._run(dict(path      = path,
                                 oligos    = pksmdl.oligos,
                                 sequences = pksmdl.sequences(...)),
                            model,
                            _end)
        except IOError as exc:
            if len(exc.args) == 1:
                msg = self.__theme.errors.get(exc.args[0], None)
                if msg is not None:
                    raise IOError(*msg) from exc
            raise

        if ret:
            self.__msg(self.__theme.start)
        return ret

    __TASKS  = 'singlestrand', 'baselinefilter', 'fittoreference', 'identification'
    __EXCEPT = DataCleaningTask, ExtremumAlignmentTask, ClippingTask
    def __complete_model(self, model, pksmdl):
        ind = max(
            (i for i, j in enumerate(model) if isinstance(j, self.__EXCEPT)),
            None
        )
        if ind is not None:
            model.insert(ind+1, ExceptionCatchingTask(exceptions = [DataCleaningException]))

        if not any(isinstance(i, pksmdl.identification.tasktype) for i in model):
            # If this methods gets called prior to the user using the peaks tab, some
            # tasks - irrelevant to the visited tabs - may have never been appended.
            # We add them now
            missing: tuple = (
                pksmdl.eventdetection,
                pksmdl.peakselection,
                *(getattr(pksmdl, i) for i in self.__TASKS if getattr(pksmdl, i).task)
            )
            while len(missing) and isinstance(model[-1], tuple(i.tasktype for i in missing)):
                missing = missing[1:]
            model = model + [deepcopy(i.configtask) for i in missing]

        ref = pksmdl.fittoreference.reference
        ind = next(
            (i for i, j in enumerate(model) if isinstance(j, FitToReferenceTask)),
            None
        )
        if ref is not None and ind is not None:
            procs                  = self.__ctrl.tasks.processors(ref, PeakSelectorTask)
            model[ind]             = _SafeTask(**model[ind].config())
            model[ind].defaultdata =  procs.data
        return model

    def __msg(self, msg):
        self.__ctrl.display.update("message", message = msg)

    @classmethod
    def _run(cls, xlscnf, model, end = None):
        "creates a Hybridstat report"
        if cls.RUNNING:
            raise IOError("running")
        cls.RUNNING = True

        if isinstance(model[-1], FitToHairpinTask):
            cache  = _createdata(*model[:-1],
                                 BeadsByHairpinTask(**model[-1].config()),
                                 HybridstatExcelTask(model     = model,
                                                     **xlscnf))
        else:
            cache  = _createdata(*model,
                                 PeakFindingExcelTask(model     = model,
                                                      **xlscnf))

        error: List[Optional[Exception]] = [None]
        def _process():
            try:
                with cls.POOLTYPE() as pool:
                    for itm in cache.run(pool = pool):
                        tuple(itm)
            except Exception as exc:
                error[0] = exc
                raise
            finally:
                cls.RUNNING = False
                if end is not None:
                    end(error[0])

        async def _thread():
            with ThreadPoolExecutor(1) as thread:
                await threadmethod(_process, pool = thread)

        spawn(_thread)
        return True

def setupio(cls):
    "sets the io up"
    if isinstance(cls, type):
        # pylint: disable=protected-access,
        def advanced(self):
            "triggers the advanced dialog"
            self._plotter.advanced()

        def ismain(self, ctrl):
            "Alignment, ... is set-up by default"
            self._ismain(ctrl, tasks = self.TASKS,
                         **setupio(getattr(self._plotter, '_model')))

        cls.TASKS    =  ('extremumalignment', 'clipping', 'eventdetection', # type: ignore
                         'peakselector', 'singlestrand', 'baselinepeakfilter')
        cls.advanced = advanced    #type: ignore
        cls.ismain   = ismain      #type: ignore
        return cls

    name = lambda i: __name__ + '.'+i
    return dict(ioopen = (slice(None, -2),
                          name('PeaksConfigGRFilesIO'),
                          name('PeaksConfigMuWellsFilesIO'),
                          name('PeaksConfigTrackIO')),
                iosave = (..., name('ConfigXlsxIO')))
