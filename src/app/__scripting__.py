#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saves stuff from session to session
"""
from   typing              import Tuple, Union, cast
from   pathlib             import Path
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

        self._ctrl.getGlobal("config").scripting.defaults = dict(gui = False, save = False)
        getattr(Tasks, 'setconfig')(self._ctrl)

    def opentrack(self, tpe = 'track'):
        "opens a gui to obtain a track"
        if self._ctrl.getGlobal('config').scripting.gui.get():
            return (self.trkdlg if tpe == 'track' else self.grdlg).open()
        return AttributeError("Operation not allowed guiven current settings")

    def writeuserconfig(self):
        "writes the config to disk"
        if self._ctrl.getGlobal('config').scripting.save.get():
            self._ctrl.writeuserconfig()

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
def save(cls, task: Task):
    "saves the task to the default config"
    cpy = deepcopy(task)
    if getattr(cpy, '__scripting_save__', lambda: True)():
        cls.getconfig()[cls(task).value].set(cpy)
        scriptapp.writeuserconfig()

@addto(Tasks, staticmethod)
def getconfig():
    "returns the config accessor"
    return scriptapp.control.getGlobal('config').tasks

@addto(Tasks, classmethod)
def setconfig(cls, cnf):
    "add default values to the config"
    cnf          = cnf.getGlobal('config').tasks
    cnf.defaults = cls.defaults()
    cnf.fittohairpin.range.defaults = dict(stretch = (900., 1400.),
                                           bias    = (-.25, .25))
    cnf.fittoreference.range.defaults = dict(stretch = (.8, 1.2),
                                             bias    = (-.15, .15))
    cnf.scripting.defaults = {'alignment.always': True,
                              'order':            None,
                              'cleaning.tasks':   None}

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
    order = cls.getconfig().scripting.order.get(default = None)
    return __old__(order)

@addto(Tasks, classmethod)
def __taskorder__(cls, __old__ = Tasks.__taskorder__):
    cnf = cls.getconfig().scripting
    old = __old__()
    return ((cls.alignment,) + old) if cnf.alignment.always.get() else old

@addto(Tasks, classmethod)
def __cleaning__(cls):
    cnf = cls.getconfig().scripting
    ret = cnf.cleaning.tasks.get()
    if ret is None:
        ret = Tasks.__base_cleaning__()

    if cnf.alignment.always.get():
        # Remove alignment as it is not an optional task.
        # It will be added back in __tasklist__
        ret = tuple(i for i in ret if i is not Tasks.alignment)
    return ret

def localcontext(**kwa) -> LocalContext:
    """
    Isolates the configuration for a period of time.

    It is **NOT THREAD SAFE**.

    For example:

    ```python
    >>> with localcontext():
    ...     # change tasks as wanted
    ...     Tasks.peakselector(align = None)
    ...     assert Tasks.peakselector.get().align is None

    >>> # changes within the localcontext have been discarded
    >>> assert Tasks.peakselector.get().align is not None
    ```
    """
    return LocalContext(scriptapp.control, **kwa)
localcontext.__doc__ = LocalContext.__doc__

@addto(Tasks)
def defaulttasklist(obj, upto, cleaned:bool = None, __old__ = Tasks.defaulttasklist):
    "Returns a default task list depending on the type of raw data"
    cnf = getattr(getattr(obj, 'tasks', None), 'config', lambda: None)()
    if cnf:
        with localcontext().update(config = cnf):
            return __old__(obj, upto, cleaned)
    return __old__(obj, upto, cleaned)

@addto(Track)
def __init__(self, *path: Union[str, Path], __old__ = Track.__init__, **kwa):
    if 'path' in kwa and len(path):
        raise RuntimeError("Path cannot be specified both in keywords and arguments")
    if 'path' in kwa:
        if isinstance(kwa['path'], (str, Path)):
            path = (kwa.pop('path'),)
        else:
            path = cast(tuple, kwa.pop('path'))

    cnf = scriptapp.control.getGlobal('css').last.path.trk
    if any(i in (Ellipsis, 'prev', '') for i in path):
        path = cnf.get()

    gui = None
    if len(path) == 0:
        gui = scriptapp.opentrack()
        if isinstance(gui, AttributeError):
            gui = None

    if path or gui:
        cnf.set(gui if gui else path[0])
        scriptapp.writeuserconfig()
    __old__(self, path = (gui if gui else path if path else ''), **kwa)

@addto(Track)
def grfiles(self):
    "access to gr files"
    paths = scriptapp.opentrack('gr')
    if isinstance(paths, AttributeError):
        raise paths
    if paths is None or len(paths) == 0:
        return
    old = self.path
    self.__init__(path = ((old,) if isinstance(old, str) else old)+paths)

# pylint: disable=no-member,invalid-name
scriptapp = default.application(main = ScriptingView, creator = lambda x: x)() # type: ignore

__all__ = ['scriptapp', 'Tasks', 'localcontext']
