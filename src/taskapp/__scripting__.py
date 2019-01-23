#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Saves stuff from session to session
"""
from   copy                    import deepcopy
from   typing                  import Tuple, List, Optional

from   data.__scripting__      import Track
from   taskmodel.application   import TasksConfig
from   taskmodel.__scripting__ import Tasks, Task
from   utils                   import initdefaults
from   utils.decoration        import addto
import taskapp.default         as     _default

class ScriptingTheme:
    """
    model for scripting
    """
    name                            = "scripting"
    save                            = False
    alignalways                     = True
    order:    Optional[List[Tasks]] = None
    cleaning: Optional[List[Tasks]] = None
    fittohairpinrange               = dict(stretch = (900., 1400.), bias = (-.25, .25))
    fittoreferencerange             = dict(stretch = (.8, 1.2),     bias = (-.15, .15))

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class ScriptingView:
    "Dummy view for scripting"
    APPNAME = 'Scripting'
    def __init__(self, ctrl):
        self._ctrl  = ctrl
        self._ctrl.theme.add(ScriptingTheme())
        self._ctrl.theme.add(TasksConfig())

    def getmodel(self, mdl, name = None, defaultmodel = False, **kwa):
        "returns the config accessor"
        theme = self._ctrl.theme
        if kwa:
            assert name is None
            theme.update(mdl, **kwa)
        if name:
            return theme.get(mdl, name, defaultmodel = defaultmodel)
        return theme.model(mdl, defaultmodel)

    def scriptingmodel(self, name = None, defaultmodel = False, **kwa):
        "returns the config accessor"
        return self.getmodel(ScriptingTheme, name, defaultmodel, **kwa)

    def tasksmodel(self, name = None, defaultmodel = False, **kwa):
        "returns the config accessor"
        return self.getmodel(TasksConfig, name, defaultmodel, **kwa)

    def writeuserconfig(self):
        "writes the config to disk"
        if self.scriptingmodel("save"):
            self._ctrl.writeuserconfig()

    def observe(self, _):
        "whatever needs to be initialized"

    def ismain(self, _):
        "Allows setting-up stuff only when the view is the main one"

    def close(self):
        "closes the application"
        self._ctrl.close()
        self._ctrl = None

    @property
    def control(self):
        "returns the controller"
        return self._ctrl

@addto(Tasks, staticmethod)
def scriptingmodel(name = None, defaultmodel = False, **kwa):
    "returns the config accessor"
    return scriptapp.scriptingmodel(name, defaultmodel, **kwa)

@addto(Tasks, staticmethod)
def tasksmodel(name = None, defaultmodel = False, **kwa):
    "returns the config accessor"
    return scriptapp.tasksmodel(name, defaultmodel, **kwa)

@addto(Tasks, classmethod)
def save(cls, task: Task):
    "saves the task to the default config"
    cpy = deepcopy(task)
    if getattr(cpy, '__scripting_save__', lambda: True)():
        name = getattr(cls, '_cnv')(cls(task).name)
        mdl  = cls.tasksmodel()
        out  = dict(mdl.tasks)
        out[name] = cpy
        cls.tasksmodel(**{mdl.instrument: out})
        scriptapp.writeuserconfig()

@addto(Tasks)
def let(self, *resets, instrument = None, **kwa) -> Task:
    """
    Same as Tasks.__call__ but saves the configuration as the default
    """
    if instrument is not None:
        old = self.tasksmodel().instrument
        self.tasksmodel(instrument = instrument)
        try:
            res = self(*resets, **kwa)
            self.save(res)
        finally:
            self.tasksmodel(instrument = old)
    else:
        res = self(*resets, **kwa)
        self.save(res)
    return res

@addto(Tasks)
def __call__(self, *resets, __old__ = Tasks.__call__, **kwa) -> Task:
    if Ellipsis in resets:
        cnf = self.default()
    else:
        mdl = self.tasksmodel()
        # pylint: disable=protected-access
        cnf = mdl.tasks.get(self._cnv(self.name), None)
    if cnf is None:
        return __old__(self, *resets, **kwa)
    res = __old__(self, *resets, current = cnf, **kwa)
    return res

@addto(Tasks, classmethod)
def defaulttaskorder(cls, __old__ = Tasks.defaulttaskorder) -> Tuple[type, ...]:
    "returns the default task order"
    return __old__(cls.scriptingmodel("order"))

@addto(Tasks, classmethod)
def __taskorder__(cls, __old__ = Tasks.__taskorder__):
    always = cls.scriptingmodel("alignalways")
    old    = __old__()
    return ((cls.alignment,) + old) if always else old

@addto(Tasks, classmethod)
def __cleaning__(cls):
    ret = cls.scriptingmodel("cleaning")
    if ret is None:
        ret = Tasks.__base_cleaning__()

    if cls.scriptingmodel("alignalways"):
        # Remove alignment as it is not an optional task.
        # It will be added back in __tasklist__
        ret = tuple(i for i in ret if i is not Tasks.alignment)
    return ret

@addto(Tasks)
def defaulttasklist(obj, upto, cleaned:bool = None, __old__ = Tasks.defaulttasklist):
    "Returns a default task list depending on the type of raw data"
    cnf = getattr(obj, 'tasks', None)
    if cnf is None:
        return __old__(obj, upto, cleaned)
    with cnf.context(obj.instrument['type'],  scriptapp.control):
        return __old__(obj, upto, cleaned)

@addto(Tasks)
def default(self, __old__ = Tasks.default) -> Task:
    "returns default tasks"
    return Tasks.defaults(self, self.tasksmodel())

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
scriptapp = _default.application(ScriptingView).open(None).topview.views[0] # type: ignore
def localcontext(**kwa):
    "allows changing the context locally. This is **not** thread safe."
    return scriptapp.control.theme.localcontext(**kwa)

__all__ = ['scriptapp', 'Tasks', 'localcontext']
