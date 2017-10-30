#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saves stuff from session to session
"""
import sys
import inspect
from   typing      import Tuple
from   copy        import deepcopy

from   view.dialog import FileDialog
from   .           import default

Tasks = sys.modules['model.__scripting__'].Tasks

_frame = None
for _frame in inspect.stack()[1:]:
    if 'importlib' not in _frame.filename:
        assert (_frame.filename == '<stdin>'
                or _frame.filename.startswith('<ipython'))
    break
del _frame

class ScriptingView:
    "Dummy view for scripting"
    APPNAME = 'Scripting'
    ISAPP   = False
    def __init__(self, **kwa):
        self._ctrl  = kwa['ctrl']
        self.trkdlg = FileDialog(filetypes = 'trk|*',
                                 config    = self._ctrl,
                                 multiple  = False,
                                 title     = "open a track file")

        self.grdlg  = FileDialog(filetypes = 'gr|*',
                                 config    = self._ctrl,
                                 multiple  = True,
                                 title     = "open a gr files")

        self._ctrl.getGlobal("config").tasks.order.scripting.default = None

        Tasks.setconfig(self._ctrl)

    def observe(self):
        "whatever needs to be initialized"

    def ismain(self):
        "Allows setting-up stuff only when the view is the main one"

    def close(self):
        "closes the application"
        self._ctrl.close()
        self._ctrl = None

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
        name = 'driftperbead' if task.onbeads else 'driftpercycle'
    else:
        for name in cls._member_names_: # pylint: disable=protected-access
            if type(task) is type(cnf[name].get(default = None)):
                assert name not in ('driftpercycle', 'driftperbead')
                break
        else:
            raise TypeError('Unknown task: '+str(task))

    cnf[name].set(deepcopy(task))
    scriptapp.control.writeuserconfig()
Tasks.save = classmethod(save)

def getconfig():
    "returns the config accessor"
    return scriptapp.control.getGlobal('config').tasks
Tasks.getconfig = staticmethod(getconfig)

def setconfig(cls, cnf):
    "add default values to the config"
    cnf = cnf.getGlobal('config').tasks
    cnf.defaults = cls.defaults()
    cnf.fittohairpin.range.defaults = dict(stretch = (900., 1400.),
                                           bias    = (-.25, .25))
    cnf.fittoreference.range.defaults = dict(stretch = (.8, 1.2),
                                             bias    = (-.15, .15))
    cnf.alignment.always.default = True

Tasks.setconfig = classmethod(setconfig)

def __call__(self, *resets, __old__ = Tasks.__call__, **kwa):
    if Ellipsis in resets:
        cnf = self.default()
    else:
        cnf = self.getconfig()[self.value].get()
    return __old__(self, *resets, current = cnf, **kwa)
Tasks.__call__ = __call__

def defaulttaskorder(cls, __old__ = Tasks.defaulttaskorder) -> Tuple[type, ...]:
    "returns the default task order"
    order = cls.getconfig().order.scripting.get(default = None)
    return __old__(order)
Tasks.defaulttaskorder = classmethod(defaulttaskorder)

def defaulttasklist(cls, paths, upto, cleaned:bool, __old__ = Tasks.defaulttasklist):
    "Returns a default task list depending on the type of raw data"
    tasks = __old__(paths, upto, cleaned)
    if cls.getconfig().alignment.always.get() is False:
        return tasks

    inst = Tasks.alignment.get()
    tpe  = type(inst)
    if any(isinstance(i, tpe) for i in tasks):
        return tasks
    if isinstance(tasks[0], type(Tasks.cleaning.get())):
        return tasks[:1]+(inst,)+tasks[1:]
    return (inst,)+tasks

Tasks.defaulttasklist = classmethod(defaulttasklist)


# pylint: disable=no-member,invalid-name
scriptapp = default.application(main = ScriptingView, creator = lambda x: x)() # type: ignore

__all__ = ['scriptapp', 'Tasks']
