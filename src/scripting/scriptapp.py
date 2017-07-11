#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saves stuff from session to session
"""
import inspect
from   copy        import deepcopy

from   view        import View
from   view.dialog import FileDialog
from   app         import Defaults
from   .task       import Tasks

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

Tasks.__doc__ = """
    Possible tasks

    These can be created as follows:

        >>> task = Tasks.alignment()
        >>> assert isinstance(task, ExtremumAlignmentTask)

    Attribute values can be set. The choice is saved for future creations
    within the session and in the next ones.  This can be reset by passing the
    attribute name or an ellipsis.

        >>> assert Tasks.peakselector().align is not None         # default value
        >>> assert Tasks.peakselector(align = None).align is None # change default
        >>> assert Tasks.peakselector().align is None             # default has changed
        >>> assert Tasks.peakselector('align').align is not None  # back to true default
        >>> assert Tasks.peakselector(align = None).align is None # change default
        >>> assert Tasks.peakselector(...) is not None            # back to true default
    """

def save(cls, task):
    "saves the task to the default config"
    cnf  = scriptapp.control.getGlobal("config").tasks
    if isinstance(task, type(cnf.driftpercycle.get())):
        name = 'driftperbeads' if task.onbeads else 'driftpercycle'
    else:
        for name in cls._member_names_: # pylint: disable=protected-access
            if type(task) is type(cnf[name].get(default = None)):
                assert name not in ('driftpercycle', 'driftperbeads')
                break
        else:
            raise TypeError('Unknown task: '+str(task))

    cnf[name].set(deepcopy(task))
    scriptapp.control.writeconfig()
Tasks.save = classmethod(save)

def __call__(self, *resets, __old__ = Tasks.__call__, **kwa):
    if Ellipsis in resets:
        cnf = self.default()
    else:
        cnf = scriptapp.control.getGlobal("config").tasks[self.value].get()
    return __old__(self, *resets, current = cnf, **kwa)
Tasks.__call__ = __call__

# pylint: disable=no-member,invalid-name
scriptapp = Defaults.application(main = ScriptingView)()

__all__ = ['scriptapp', 'Tasks']
