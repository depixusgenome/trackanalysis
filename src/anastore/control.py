#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Sets things up for the taskcontroller"

from typing             import Union, Tuple
from control.taskio     import TaskIO
from utils              import initdefaults
from utils.logconfig    import getLogger
from .api               import load, dump

LOGS = getLogger(__name__)

class AnaIO(TaskIO):
    "Ana IO"
    EXT = ('ana',)
    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        u"opens an ana file"
        if isinstance(path, tuple):
            if len(path) != 1:
                return None
            path = path[0]

        out = load(path)
        if out is not None and len(model):
            raise NotImplementedError()
        if out is not None:
            LOGS.info(f'{type(self).__name__} loading {path}')
        return [out] if isinstance(out, dict) else out

    def save(self, path:str, models):
        u"closes an ana file"
        if len(models):
            LOGS.info('%s saving %s', type(self).__name__, path)
            dump(models, path)
        else:
            raise IOError("Nothing to save", "warning")
        return True

class ConfigAnaIOTheme:
    "define how to save the json data"
    name         = "configanaio"
    indent       = 4
    ensure_ascii = False
    sort_keys    = True
    @initdefaults(frozenset(locals()) - {'name'})
    def __init__(self, **_):
        pass

class ConfigAnaIO(AnaIO):
    "Ana IO"
    EXT = ('ana',)
    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        self._ctrl  = ctrl
        self._model = ConfigAnaIOTheme()
        ctrl.theme.add(self._model)

    def save(self, path:str, models):
        u"closes an ana file"
        curr   = self._ctrl.display.get("tasks", "roottask")
        models = [i for i in models if curr is i[0]]

        if len(models):
            ctrl = getattr(self._ctrl, 'globals', self._ctrl)
            cnf  = ctrl.writeconfig(None, dict).get('config', {})
            cnf  = {i: j for i, j in cnf.items() if i.startswith("tasks")}
            dump(dict(tasks = models, config = cnf), path, **self._model.__dict__)
        else:
            raise IOError("Nothing to save", "warning")
        return True
