#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from typing         import List, Tuple, TYPE_CHECKING   # pylint: disable=unused-import
from copy           import deepcopy
from bokeh.document import Document                     # pylint: disable=unused-import
from bokeh.models   import Widget, Button
from .              import dialog

class AdvancedWidgetMixin:
    "A button to access the modal dialog"
    _TITLE = None # type: str
    _BODY  = None # type: Tuple[Tuple[str, ...]]
    def __init__(self):
        self.__widget = None # type: Optional[Button]
        self.__doc    = None # type: Optional[Document]
        self.__action = None # type: Optional[type]
        assert self._TITLE is not None
        assert self._BODY is not None
        self.config.root.keypress.advanced.default = 'Alt-a'
        self.css.dialog.defaults = dict(title  = self._TITLE,
                                        button = 'Advanced',
                                        body   = tuple(i for i, _ in self._BODY))
        if TYPE_CHECKING:
            self.css    = None
            self._ctrl  = None

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
        self.__outp = {} # type: Dict[str, Dict[str, Any]]

    def __enter__(self, *args):
        self.__outp.clear()
        super().__enter__()

    def __exit__(self, tpe, val, bkt):
        for key, elems in self.__outp.items():
            getattr(self._model, key).update(**elems)

        super().__exit__(tpe, val, bkt)

    def _args(self, **_):
        return super()._args(model = self, **_)

    __none = type('_None', (), {})
    @staticmethod
    def attr(akeys:str, getter = None, setter = None):
        "sets a task's attribute"
        keys = akeys.split('.')
        assert len(keys) >= 2
        # pylint: disable=protected-access
        def _get(self):
            mdl = getattr(self._model, keys[0])
            mdl = getattr(mdl, 'task', mdl)
            for key in keys[1:]:
                mdl = getattr(mdl, key)
            return mdl if getter is None else getter(mdl)

        def _set(self, val):
            tsk = getattr(self._model, keys[0]).task
            if len(keys) == 2:
                val = val if setter is None else setter(tsk, val)
                self.__outp.setdefault(keys[0], {})[keys[1]] = val
            else:
                mdl = self.__outp.setdefault(keys[0], {}).get(keys[1], self.__none)
                if mdl is self.__none:
                    mdl = deepcopy(getattr(tsk, keys[1]))
                    self.__outp[keys[0]][keys[1]] = mdl

                for key in keys[2:-1]:
                    mdl = getattr(mdl, key)

                if setter is None:
                    setattr(mdl, keys[-1], val)
                else:
                    setattr(mdl, keys[-1], setter(mdl, val))

        return property(_get, _set)

    @classmethod
    def none(cls, akeys:str):
        "sets a task's attribute to None or the default value"
        key = akeys.split('.')[-1]
        def _setter(obj, val):
            if not val:
                return None
            attr = getattr(obj, key)
            if attr is None:
                attr = deepcopy(getattr(type(obj), key))
            return attr

        return cls.attr(akeys, lambda i: i is not None, _setter)
