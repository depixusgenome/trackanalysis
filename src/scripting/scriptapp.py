#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saves stuff from session to session
"""
from copy                   import deepcopy
from enum                   import Enum
import inspect

from utils                  import update

from model.task                 import DataSelectionTask, CycleCreatorTask, Task
from cordrift.processor         import DriftTask
from eventdetection.processor   import ExtremumAlignmentTask, EventDetectionTask
from peakfinding.processor      import PeakSelectorTask
from peakcalling.processor      import FitToHairpinTask

from   view                   import View
from   view.dialog            import FileDialog
from   app                    import Defaults

_frame = None
for _frame in inspect.stack()[1:]:
    if 'importlib' not in _frame.filename:
        assert (_frame.filename == '<stdin>'
                or _frame.filename.startswith('<ipython'))
    break
del _frame

class ScriptingView(View):
    "Dummy view for scripting"
    APPNAME = 'Scripting'
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.trkdlg  = FileDialog(filetypes = 'trk|*',
                                  config    = self._ctrl,
                                  multiple  = False,
                                  title     = "open a track file")

        self.grdlg   = FileDialog(filetypes = 'gr|*',
                                  config    = self._ctrl,
                                  multiple  = True,
                                  title     = "open a gr files")

        cnf = self._ctrl.getGlobal("config").tasks
        cnf.defaults = dict(selection      = DataSelectionTask(),
                            alignment      = ExtremumAlignmentTask(),
                            driftperbead   = DriftTask(onbeads = True),
                            driftpercycle  = DriftTask(onbeads = False),
                            cycles         = CycleCreatorTask(),
                            eventdetection = EventDetectionTask(),
                            peakselector   = PeakSelectorTask(),
                            fittohairpin   = FitToHairpinTask())

    @property
    def control(self):
        "returns the controller"
        return self._ctrl

class Tasks(Enum):
    "possible tasks"
    selection      = 'selection'
    alignment      = 'alignment'
    driftperbead   = 'driftperbead'
    driftpercycle  = 'driftpercycle'
    cycles         = 'cycles'
    eventdetection = 'eventdetection'
    peakselector   = 'peakselector'
    fittohairpin   = 'fittohairpin'

    @classmethod
    def save(cls, task):
        "saves the task to the default config"
        cnf  = scriptapp.control.getGlobal("config").tasks
        if isinstance(task, type(cls.driftpercycle)):
            name = 'driftperbeads' if task.onbeads else 'driftpercycle'
        else:
            for name in cls._member_names_: # pylint: disable=no-member
                if type(task) is type(cnf[name].get(default = None)):
                    break
            else:
                raise TypeError('Unknown task: '+str(task))

        cnf[name].set(deepcopy(task))
        scriptapp.control.writeconfig()

    @classmethod
    def create(cls, arg, **kwa):
        "returns the task associated to the argument"
        if isinstance(arg, (str, cls)):
            return cls(arg)(**kwa)

        elif isinstance(arg, tuple):
            return cls(arg[0])(**arg[1], **kwa)

        else:
            assert isinstance(arg, Task)
            if len(kwa):
                return update(deepcopy(arg), **kwa)
            return arg

    def __call__(self, **kwa):
        cnf  = scriptapp.control.getGlobal("config").tasks
        task = update(deepcopy(cnf[self.value].get()), **kwa)
        self.save(task)
        return task

    class _TaskGetter:
        def __get__(self, obj, tpe):
            return tpe.create if obj is None else obj

    get = _TaskGetter()

# pylint: disable=no-member,invalid-name
scriptapp = Defaults.application(main = ScriptingView)()

__all__ = ['scriptapp', 'Tasks']
