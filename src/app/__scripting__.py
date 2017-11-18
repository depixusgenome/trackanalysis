#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saves stuff from session to session
"""
from   typing              import Tuple
from   copy                import deepcopy

from   utils.decoration    import addto
from   view.dialog         import FileDialog
from   data.__scripting__  import Track
from   model.__scripting__ import Tasks, Task
from   model.globals       import LocalContext
from   .                   import default

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

        self._ctrl.getGlobal("config").path.gui.default              = False
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
    cnf = scriptapp.control.getGlobal("config").tasks
    if isinstance(task, type(cnf.driftpercycle.get())):
        name = 'driftperbead' if task.onbeads else 'driftpercycle'
    else:
        for name in cls._member_names_: # pylint: disable=protected-access
            if type(task) is type(cnf[name].get(default = None)):
                assert name not in ('driftpercycle', 'driftperbead')
                break
        else:
            raise TypeError('Unknown task: '+str(task))

    cpy = deepcopy(task)
    if getattr(cpy, '__scripting_save__', lambda: True)():
        return

    cnf[name].set(cpy)
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

@addto(Tasks, staticmethod)
def __tasklist__(__old__ = Tasks.__tasklist__()):
    return __old__

@addto(Tasks, classmethod)
def __cleaning__(cls, __old__ = Tasks.__cleaning__()):
    return __old__[:-1] if cls.getconfig().alignment.always.get() else __old__

@addto(Tasks)
def defaulttasklist(obj, upto, cleaned:bool = None, __old__ = Tasks.defaulttasklist):
    "Returns a default task list depending on the type of raw data"
    if getattr(obj, 'tasks', None):
        with LocalContext(scriptapp.control).update(config = getattr(obj, 'tasks')):
            return __old__(obj, upto, cleaned)
    return __old__(obj, upto, cleaned)

@addto(Track)
def __init__(self, *path, __old__ = Track.__init__, **kwa):
    cnf = scriptapp.control.getGlobal('css').last.path.trk
    if any(i in (Ellipsis, 'prev', '') for i in path):
        path = cnf.get()

    gui = None
    if len(path) == 0 and scriptapp.control.getGlobal('css').path.gui.get():
        gui = scriptapp.trkdlg.open()

    if path or gui:
        cnf.set(gui if gui else path[0])
        scriptapp.control.writeuserconfig()
    __old__(self, path = (gui if gui else path if path else ''), **kwa)

@addto(Track)
def grfiles(self):
    "access to gr files"
    if not scriptapp.control.getGlobal('css').gui.get():
        raise AttributeError("Operation not allowed guiven current settings")
    paths = scriptapp.grdlg.open()
    if paths is None or len(paths) == 0:
        return
    old = self.path
    self.__init__(path = ((old,) if isinstance(old, str) else old)+paths)

# pylint: disable=no-member,invalid-name
scriptapp = default.application(main = ScriptingView, creator = lambda x: x)() # type: ignore

__all__ = ['scriptapp', 'Tasks']
