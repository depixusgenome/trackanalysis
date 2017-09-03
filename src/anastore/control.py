#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Sets things up for the taskcontroller"

from typing             import Union, Tuple
from control.taskio     import TaskIO, currentmodelonly
from .                  import load, dump

class AnaIO(TaskIO):
    "Ana IO"
    EXT = ('ana',)
    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        self._css          = ctrl.getGlobal('css').anastore
        self._css.defaults = {'indent': 4, 'ensure_ascii': False, 'sort_keys': True}

    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        u"opens an ana file"
        if isinstance(path, tuple):
            if len(path) != 1:
                return None
            path = path[0]

        out = load(path)
        if out is not None and len(model):
            raise NotImplementedError()
        return out

    def save(self, path:str, models):
        u"closes an ana file"
        if len(models):
            dump(models, path, **self._css.getitems(...))
        else:
            raise IOError("Nothing to save", "warning")
        return True

ConfigAnaIO = currentmodelonly(AnaIO)
