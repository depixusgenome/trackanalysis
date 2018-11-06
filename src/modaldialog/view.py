#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from typing             import Dict, List, Tuple, Any, Union
from abc                import ABC, abstractmethod
from copy               import deepcopy
from bokeh.document     import Document
from bokeh.models       import Widget, Button
from view.fonticon      import FontIcon
from utils              import initdefaults
from utils.logconfig    import getLogger
from .                  import dialog
LOGS               = getLogger(__name__)

class AdvancedTab:
    "a tab in the widget"
    __inds = 0
    def __init__(self, title:str, *items: Tuple[str, ...]) -> None:
        self.body    = items
        self.title   = title
        # pylint: disable=protected-access
        self.ind     = self.__class__.__inds
        self.__class__.__inds += 1

    def htmltitle(self, ind) -> str:
        "return the html version of the title"
        fcn  = "Bokeh.DpxModal.prototype.clicktab"
        head = "cur" if ind else ""
        return ("<button type='button' class='bk-bs-btn bk-bs-btn-default "
                +f"bbm-dpx-{head}btn' id='bbm-dpx-btn-{self.ind}'"
                +f'onclick="{fcn}({self.ind})">'
                +self.title +"</button>")

    def htmlbody(self, ind) -> str:
        "return the html version of the body"
        def _elem(val):
            if isinstance(val, tuple):
                return f'<td style="{val[0]}">'+val[1]+'</td>'
            return f'<td>'+val+'</td>'

        head = 'curtab' if ind else 'hidden'
        return ('<table class="bbm-dpx-'+head+f'" id="bbm-dpx-tab-{self.ind}">'
                +''.join('<tr>' + ''.join(_elem(i) for i in j) + '</tr>'
                         for j in self.body)
                + '</table>')

    @staticmethod
    def tohtml(tabs: List['AdvancedTab']):
        "return html"
        return ("<div class='dpx-span'>"
                +"".join(j.htmltitle(i == 0) for i, j in enumerate(tabs))+"</div>"
                +"".join(j.htmlbody(i == 0)  for i, j in enumerate(tabs)))


AdvancedWidgetBody = Union[Tuple[Tuple[str, ...],...], Tuple[AdvancedTab,...]]

class AdvancedWidgetTheme:
    "AdvancedWidgetTheme"
    name   = "advancedwidget"
    width  = 280
    height = 20
    label  = ""
    icon   = "cog"
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class AdvancedWidget(ABC):
    "A button to access the modal dialog"
    __widget: Button
    __doc:    Document
    __action: type
    def __init__(self, ctrl):
        ctrl.theme.updatedefaults('keystroke', advanced = 'Alt-a')
        self._theme = ctrl.theme.add(AdvancedWidgetTheme(), False)

    @abstractmethod
    def _body(self) -> AdvancedWidgetBody:
        pass

    @abstractmethod
    def _title(self) -> str:
        pass

    def _args(self, **kwa) -> Dict[str, Any]:
        model = kwa.get('model', self)
        def _default(keys):
            desc = getattr(model.__class__, keys[0].split('|')[0], None)
            if hasattr(desc, 'getdefault'):
                mdl = desc.getdefault(model)
                for key in keys[1:]:
                    mdl = getattr(mdl, key)
                return mdl, True
            return None, False

        def _value(keys):
            mdl = model
            for key in keys:
                mdl = getattr(mdl, key.split('|')[0])
            return mdl

        def _add(title, val):
            keys        = val[val.find('(')+1:val.rfind(')')].split('.')
            dflt, found = _default(keys)
            if not found or dflt == _value(keys):
                return title, '', val

            if '|' in val:
                opts = val[val.find('(')+1:val.find(')')]
                disp = dict(i.split(':') for i in opts.split('|')[1:])[str(dflt)]
            else:
                try:
                    disp = (' '  if dflt is None  else
                            '✓'  if dflt is True  else
                            '▢'  if dflt is False else
                            dflt if isinstance(dflt, str) else
                            ('%'+val[val.rfind(')')+1:]) % dflt)
                except TypeError:
                    disp = str(dflt)

            return title, f'({disp})', val

        bdy  = self._body()
        if len(bdy) and isinstance(bdy[0], AdvancedTab):
            for k in bdy:
                k.body = tuple(_add(i, j)  for i, j in k.body) # type: ignore
        else:
            bdy = tuple(_add(i, j)  for i, j in bdy) # type: ignore


        args = dict(title   = self._title(),
                    context = lambda title: self,
                    body    = bdy)
        args.update(kwa)
        return args

    def on_click(self):
        "modal dialog for configuration"
        if not self.__widget.disabled:
            dialog(self.__doc, **self._args())

    @staticmethod
    def reset(_):
        "nothing to do"
        return

    def addtodoc(self, _1, ctrl, *_) -> List[Widget]:
        "creates the widget"
        self.__widget = Button(width  = self._theme.width,
                               height = self._theme.height,
                               label  = self._theme.label,
                               icon   = (None if self._theme.icon is None else
                                         FontIcon(iconname = self._theme.icon)))
        self.__widget.on_click(self.on_click)
        self.__action = ctrl.action.withcalls(self._title())
        return [self.__widget]

    def __enter__(self):
        self.__action.__enter__()

    def __exit__(self, tpe, val, bkt):
        self.__action.__exit__(tpe, val, bkt)

    def callbacks(self, doc):
        "adding callbacks"
        self.__doc = doc

    def ismain(self, ctrl):
        "setup for when this is the main show"
        ctrl.display.updatedefaults('keystroke', advanced = self.on_click)

class TaskDescriptor:
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

    def get(self, obj, wherefrom = "default"):
        """
        Gets the attribute in the task.

        Use config = True to access the default value
        """
        mdl = self.__model(obj)
        mdl = (getattr(mdl, 'task', mdl) if wherefrom == "model"  else
               mdl.configtask            if wherefrom == "config" else
               mdl.defaultconfigtask)

        for key in self._keys[1:]:
            mdl = getattr(mdl, key)
        return mdl if self._fget is None else self._fget(mdl)

    getdefault = get

    def __get__(self, obj, tpe):
        return self if obj is None else self.get(obj, 'model')

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

class AdvancedTaskWidget(AdvancedWidget):
    "Means for configuring tasks with a modal dialog"
    _model: Any
    def __init__(self, ctrl):
        super().__init__(ctrl)
        self.__outp: Dict[str, Dict[str, Any]] = {}

    @abstractmethod
    def _body(self) -> AdvancedWidgetBody:
        pass

    @abstractmethod
    def _title(self) -> str:
        pass

    def __enter__(self):
        self.__outp.clear()
        super().__enter__()

    def __exit__(self, tpe, val, bkt):
        LOGS.debug("%s output => %s", self._title(), self.__outp)
        for key, elems in self.__outp.items():
            getattr(self._model, key).update(**elems)

        super().__exit__(tpe, val, bkt)

    def _args(self, **kwa) -> Dict[str, Any]:
        kwa.setdefault('model', self)
        return super()._args(**kwa)

    def _get_output(self):
        return self.__outp

    @classmethod
    def attr(cls, akeys:str, fget = None, fset = None):
        "sets a task's attribute"
        return TaskDescriptor(akeys, fget, fset)

    @classmethod
    def none(cls, akeys:str):
        "sets a task's attribute to None or the default value"
        key = akeys.split('.')[-1]
        def _fset(obj, val):
            if val is False:
                return None

            attr = getattr(obj, key)
            if attr is None:
                attr = deepcopy(getattr(type(obj), key))
            return attr

        return TaskDescriptor(akeys, lambda i: i is not None, _fset)
