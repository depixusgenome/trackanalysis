#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saves stuff from session to session
"""
from   typing               import Tuple
from   copy                 import deepcopy

from   utils.decoration     import addto
from   view.dialog          import FileDialog
from   model.__scripting__  import Tasks, Task
from   .                    import default

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

        getattr(Tasks, 'setconfig')(self._ctrl)

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

@addto(Tasks, classmethod)
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

@addto(Tasks, staticmethod)
def getconfig():
    "returns the config accessor"
    return scriptapp.control.getGlobal('config').tasks

@addto(Tasks, classmethod)
def setconfig(cls, cnf):
    "add default values to the config"
    cnf = cnf.getGlobal('config').tasks
    cnf.defaults = cls.defaults()
    cnf.fittohairpin.range.defaults = dict(stretch = (900., 1400.),
                                           bias    = (-.25, .25))
    cnf.fittoreference.range.defaults = dict(stretch = (.8, 1.2),
                                             bias    = (-.15, .15))
    cnf.alignment.always.default = True

@addto(Tasks)
def __call__(self, *resets, __old__ = Tasks.__call__, **kwa) -> Task:
    if Ellipsis in resets:
        cnf = self.default()
    else:
        cnf = self.getconfig()[self.value].get(default = None)
    if cnf is None:
        return __old__(self, *resets, **kwa)
    res = __old__(self, *resets, current = cnf, **kwa)
    self.save(res)
    return res

@addto(Tasks, classmethod)
def defaulttaskorder(cls, __old__ = Tasks.defaulttaskorder) -> Tuple[type, ...]:
    "returns the default task order"
    order = cls.getconfig().order.scripting.get(default = None)
    return __old__(order)

@addto(Tasks, classmethod)
def defaulttasklist(cls, paths, upto, cleaned:bool, __old__ = Tasks.defaulttasklist):
    "Returns a default task list depending on the type of raw data"
    tasks = __old__(paths, upto, cleaned)
    if cls.getconfig().alignment.always.get() is False:
        return tasks

    inst = Tasks.alignment.get()
    tpe  = type(inst)
    if any(isinstance(i, tpe) for i in tasks):
        return tasks
    if len(tasks) > 0 and isinstance(tasks[0], type(Tasks.cleaning.get())):
        return tasks[:1]+(inst,)+tasks[1:]
    return (inst,)+tasks

# pylint: disable=no-member,invalid-name
scriptapp = default.application(main = ScriptingView, creator = lambda x: x)() # type: ignore

__all__ = ['scriptapp', 'Tasks']
