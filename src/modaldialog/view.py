#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from typing             import Dict, List, Tuple, Any, TYPE_CHECKING
from abc                import ABC
from copy               import deepcopy
from bokeh.document     import Document                     # pylint: disable=unused-import
from bokeh.models       import Widget, Button
from utils.logconfig    import getLogger
from .                  import dialog
LOGS   = getLogger(__name__)
T_BODY = Tuple[Tuple[str, str],...]

class AdvancedWidgetMixin(ABC):
    "A button to access the modal dialog"
    _TITLE : str    = None
    _BODY  : T_BODY = None
    def __init__(self):
        self.__widget: Button   = None
        self.__doc:    Document = None
        self.__action: type     = None
        assert self._TITLE is not None
        assert self._BODY is not None
        self.config.root.keypress.advanced.default = 'Alt-a'
        self.css.dialog.defaults = dict(title  = self._TITLE,
                                        button = 'Advanced',
                                        body   = tuple(i for i, _ in self._BODY))
        if TYPE_CHECKING:
            self.css:   Any = None
            self._ctrl: Any = None

    def _args(self, **kwa):
        css  = self.css.dialog
        args = dict(title   = css.title.get(),
                    context = lambda title: self,
                    body    = tuple(zip(css.body.get(), tuple(i for _, i in self._BODY))))
        args.update(kwa)
        return args

    def on_click(self):
        "modal dialog for configuration"
        dialog(self.__doc, **self._args())

    @staticmethod
    def reset(_):
        "nothing to do"
        return

    def create(self, action) -> List[Widget]:
        "creates the widget"
        width  = self.css.input.width.get()
        height = self.css.input.height.get()
        self.__widget = Button(width = width, height = height,
                               label = self.css.dialog.button.get())
        self.__widget.on_click(self.on_click)
        self.__action = action().withcalls(self.css.dialog.title.get())
        return [self.__widget]

    def __enter__(self):
        self.__action.__enter__()

    def __exit__(self, tpe, val, bkt):
        self.__action.__exit__(tpe, val, bkt)

    def callbacks(self, doc):
        "adding callbacks"
        self.__doc = doc

    def ismain(self, keys):
        "setup for when this is the main show"
        keys.addKeyPress(('keypress.advanced', self.on_click))

class AdvancedTaskMixin(AdvancedWidgetMixin):
    "Means for configuring tasks with a modal dialog"
    def __init__(self):
        super().__init__()
        self.__outp: Dict[str, Dict[str, Any]] = {}

    def __enter__(self):
        self.__outp.clear()
        super().__enter__()

    def __exit__(self, tpe, val, bkt):
        LOGS.debug(self._TITLE+ " output => %s", self.__outp)
        for key, elems in self.__outp.items():
            getattr(self._model, key).update(**elems)

        super().__exit__(tpe, val, bkt)

    def _args(self, **_):
        return super()._args(model = self, **_)

    def _get_output(self):
        return self.__outp

    class TaskAcccessor:
        "Access to a task"
        __slots__ = ('_keys', '_fget', '_fset')
        __none    = type('_None', (), {})
        def __init__(self, akeys:str, fget = None, fset = None) -> None:
            self._keys = akeys.split('.')
            self._fget = fget
            self._fset = fset
            assert len(self._keys) >= 2

        def __model(self, obj):
            return getattr(obj._model, self._keys[0]) # pylint: disable=protected-access

        def __get__(self, obj, tpe):
            if obj is None:
                return self

            mdl = self.__model(obj)
            mdl = getattr(mdl, 'task', mdl)
            for key in self._keys[1:]:
                mdl = getattr(mdl, key)
            return mdl if self._fget is None else self._fget(mdl)

        def __set__(self, obj, val):
            tsk  = self.__model(obj).task
            outp = obj._get_output() # pylint: disable=protected-access
            if len(self._keys) == 2:
                val = val if self._fset is None else self._fset(tsk, val)
                outp.setdefault(self._keys[0], {})[self._keys[1]] = val
            else:
                mdl = outp.setdefault(self._keys[0], {}).get(self._keys[1], self.__none)
                if mdl is self.__none:
                    mdl = deepcopy(getattr(tsk, self._keys[1]))
                    outp[self._keys[0]][self._keys[1]] = mdl

                for key in self._keys[2:-1]:
                    mdl = getattr(mdl, key)

                if self._fset is None:
                    setattr(mdl, self._keys[-1], val)
                else:
                    setattr(mdl, self._keys[-1], self._fset(mdl, val))

    @classmethod
    def attr(cls, akeys:str, fget = None, fset = None):
        "sets a task's attribute"
        return cls.TaskAcccessor(akeys, fget, fset)

    @classmethod
    def none(cls, akeys:str):
        "sets a task's attribute to None or the default value"
        key = akeys.split('.')[-1]
        def _fset(obj, val):
            if val:
                return None

            attr = getattr(obj, key)
            if attr is None:
                attr = deepcopy(getattr(type(obj), key))
            return attr

        return cls.TaskAcccessor(akeys, lambda i: i is not None, _fset)
