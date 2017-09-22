#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"IO for peaksplot"
from typing                          import (Optional, Tuple, # pylint: disable=unused-import
                                             Union, List)
from pathlib                         import Path
from copy                            import deepcopy
from concurrent.futures              import ProcessPoolExecutor, ThreadPoolExecutor

from control.processor.utils         import ExceptionCatchingTask
from control.taskcontrol             import create as _createdata
from control.taskio                  import (ConfigTrackIO, ConfigGrFilesIO, TaskIO,
                                             currentmodelonly)
from cleaning.processor              import DataCleaningTask, DataCleaningException
from peakfinding.reporting.processor import PeakFindingExcelTask
from peakcalling.processor           import FitToHairpinTask, BeadsByHairpinTask

from view.base                       import spawn, threadmethod
from view.dialog                     import FileDialog

from utils.logconfig                 import getLogger
from utils.gui                       import startfile

from ..reporting.processor           import HybridstatExcelTask
from ._model                         import IdentificationModelAccess, PeaksPlotModelAccess

LOGS = getLogger(__name__)

class _PeaksIOMixin:
    def __init__(self, ctrl):
        type(self).__bases__ [1].__init__(self, ctrl)
        self.__model = IdentificationModelAccess(ctrl)

    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        "opens a track file and adds a alignment"
        # pylint: disable=no-member
        items = type(self).__bases__[1].open(self, path, model) # type: ignore

        if items is not None:
            task = self.__model.defaultidenfication
            if task is not None:
                items[0] += (task,)
        return items

class PeaksConfigTrackIO(_PeaksIOMixin, ConfigTrackIO):
    "selects the default tasks"

class PeaksConfigGRFilesIO(_PeaksIOMixin, ConfigGrFilesIO):
    "selects the default tasks"

FileDialog.DEFAULTS['pkz'] = (u'pickled report', '.pkz')
@currentmodelonly
class ConfigXlsxIO(TaskIO):
    "Ana IO saving only the current project"
    EXT      = 'xlsx', 'csv', 'pkz'
    RUNNING  = False
    POOLTYPE = ProcessPoolExecutor
    def __init__(self, ctrl):
        super().__init__(ctrl)
        self.__model = PeaksPlotModelAccess(ctrl)
        self.__msg   = ctrl.getGlobal('project').message
        self.__css   = ctrl.getGlobal('css').title.hybridstatreport

    @staticmethod
    def setup(ctrl):
        "sets-up default global values"
        css = ctrl.css.root.title.hybridstatreport
        css.defaults = {'start': (u'Report in progress ...', 'normal')}
        css = css.errors
        css.defaults = {'running': ("Can only create one report at a time", "warning")}

    def save(self, path:str, models):
        "creates a Hybridstat report"
        def _end(exc):
            if exc is None and not Path(path).exists():
                exc = IOError("Report file created but not not found!")

            if isinstance(exc, IOError) and len(exc.args) == 1:
                if len(exc.args) == 1:
                    msg = self.__css.errors.get(exc.args[0], default = None)
                    if msg is not None:
                        self.__msg.set(msg)
                        LOGS.debug('Failed report creation with %s', msg[0])
                        return
            if exc is not None:
                LOGS.exception(exc)
            else:
                startfile(path)
            self.__msg.set(exc)

        model = self.__complete_model(list(models[0]))
        try:
            LOGS.info('%s saving %s', type(self).__name__, path)
            ret = self._run(dict(path      = path,
                                 oligos    = self.__model.oligos,
                                 sequences = self.__model.sequences),
                            model,
                            _end)
        except IOError as exc:
            if len(exc.args) == 1:
                msg = self.__css.errors.get(exc.args[0], default = None)
                if msg is not None:
                    raise IOError(*msg) from exc
            raise

        if ret:
            self.__msg.set(self.__css.start.get())
        return ret

    def __complete_model(self, model):
        ind = next((i for i, j in enumerate(model) if isinstance(j, DataCleaningTask)),
                   None)
        if ind is not None:
            model.insert(ind+1, ExceptionCatchingTask(exceptions = [DataCleaningException]))

        if isinstance(model[-1], self.__model.identification.tasktype):
            return model

        missing = (self.__model.eventdetection,
                   self.__model.peakselection) # type: Tuple
        while len(missing):
            if not isinstance(model[-1], tuple(i.tasktype for i in missing)):
                return model + [deepcopy(i.configtask.get()) for i in missing]
            missing = missing[1:]
        return model

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

        for itm in cache.run():
            tuple(itm)

        error = [None] # type: List[Optional[Exception]]
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

def setupio(ctrl):
    "sets the io up"
    ConfigXlsxIO.setup(ctrl)
    name = lambda i: __name__ + '.'+i
    return dict(ioopen = (slice(None, -2),
                          name('PeaksConfigGRFilesIO'),
                          name('PeaksConfigTrackIO')),
                iosave = (..., name('ConfigXlsxIO')))
