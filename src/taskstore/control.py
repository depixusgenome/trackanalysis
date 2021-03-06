#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Sets things up for the taskcontroller"

from typing             import Tuple, Union

from data.trackio       import instrumenttype
from taskcontrol.taskio import TaskIO
from utils              import initdefaults
from utils.logconfig    import getLogger
from .                  import dump, load

LOGS = getLogger(__name__)

class AnaIO(TaskIO):
    "Ana IO"
    EXT = ('ana',)
    def open(self, path:Union[str, Tuple[str,...]], model:tuple): # type: ignore
        "opens an ana file"
        if isinstance(path, tuple):
            if len(path) != 1:
                return None
            path = path[0]

        out = load(path)
        if out is not None and len(model):
            raise NotImplementedError()
        if out is not None:
            LOGS.info("%s loading %s", type(self).__name__, path)
        return [out] if isinstance(out, dict) else out

    def save(self, path:str, models):
        "closes an ana file"
        if len(models):
            LOGS.info('%s saving %s', type(self).__name__, path)
            dump(models, path)
        else:
            raise IOError("Nothing to save", "warning")
        return True

class ConfigAnaIOConfig:
    "define how to save the json data"
    name         = "anaio"
    indent       = 4
    ensure_ascii = False
    sort_keys    = True
    @initdefaults(frozenset(locals()) - {'name'})
    def __init__(self, **_):
        pass

class ConfigAnaIO(AnaIO):
    "Ana IO"
    EXT = ('ana',)
    _model: ConfigAnaIOConfig
    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        self._ctrl  = ctrl
        self._model = ctrl.theme.add(ConfigAnaIOConfig(), False)

    def open(self, path:Union[str, Tuple[str,...]], model:tuple): # type: ignore
        "opens an ana file"
        out = super().open(path, model)
        if not out:
            return None

        if not (isinstance(out, list)
                and len(out) == 1
                and isinstance(out[0], dict)
                and "tasks" in out[0]):
            return None
        self._ctrl.display.handle("openanafile",
                                  args = {"model": out[0], 'controller': self._ctrl})
        return out[0]['tasks']

    def save(self, path:str, models):
        "closes an ana file"
        curr   = self._ctrl.display.get("tasks", "roottask")
        models = [i for i in models if curr is i[0]]

        if len(models):
            info = {'tasks': models}
            self._ctrl.display.handle("saveanafile",
                                      args = {"model":      info,
                                              'controller': self._ctrl})
            dump(info, path, **self._model.__dict__)
        else:
            raise IOError("Nothing to save", "warning")
        return True

    @staticmethod
    def instrumenttype(path: str) -> str:
        "return the instrument type"
        return instrumenttype(super().open(path, ())[0]['tasks'][0])  # type: ignore
