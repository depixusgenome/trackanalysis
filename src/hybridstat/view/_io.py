#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"IO for peaksplot"
from typing                     import Tuple, Union
from concurrent.futures         import ProcessPoolExecutor, ThreadPoolExecutor

from control.taskcontrol        import create as _createdata
from control.taskio             import (ConfigTrackIO, ConfigGrFilesIO, TaskIO,
                                        currentmodelonly)
from peakcalling.processor      import FitToHairpinTask, BeadsByHairpinTask

from view.base                  import spawn, threadmethod
from view.dialog                import FileDialog

from utils.gui                  import startfile

from ..reporting.processor      import HybridstatExcelTask
from ._model                    import IdentificationModelAccess, PeaksPlotModelAccess

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
        css.defaults = {'running': ("Can only create one report at a time", "warning"),
                        'missing': ('Oligos or sequences left undefined', "warning")}

    def save(self, path:str, models):
        "creates a Hybridstat report"
        try:
            ret = self._run(dict(path      = path,
                                 oligos    = self.__model.oligos,
                                 sequences = self.__model.sequences),
                            models[0],
                            lambda: startfile(path))
        except IOError as exc:
            if len(exc.args) == 1:
                msg = self.__css.errors.get(exc.args[0], default = None)
                if msg is not None:
                    raise IOError(*msg) from exc
            raise
        if ret:
            self.__msg.set(self.__css.start.get())
        return ret

    @classmethod
    def _run(cls, xlscnf, model, end = None):
        "creates a Hybridstat report"
        if cls.RUNNING:
            raise IOError("running")
        cls.RUNNING = True

        if not isinstance(model[-1], FitToHairpinTask):
            raise IOError('missing')

        cache  = _createdata(*model[:-1],
                             BeadsByHairpinTask(**model[-1].config()),
                             HybridstatExcelTask(model     = model,
                                                 **xlscnf))

        def _process():
            try:
                with cls.POOLTYPE() as pool:
                    for itm in cache.run(pool = pool):
                        tuple(itm)
            finally:
                cls.RUNNING = False

        async def _thread():
            with ThreadPoolExecutor(1) as thread:
                await threadmethod(_process, pool = thread)
            if end is not None:
                end()

        spawn(_thread)
        return True

def setupio(ctrl):
    "sets the io up"
    ConfigXlsxIO.setup(ctrl)

    tasks = ctrl.config.root.tasks
    vals  = (tuple(tasks.io.open.get()[:-2])
             + (__name__+'.PeaksConfigGRFilesIO', __name__+'.PeaksConfigTrackIO'))
    tasks.io.open.default = vals

    vals = (tuple(tasks.io.save.get())+(__name__+'.ConfigXlsxIO',))
    tasks.io.save.default = vals
