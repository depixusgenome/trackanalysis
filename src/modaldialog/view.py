#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from typing             import Dict, List, Tuple, Any, Union, Optional, Callable, cast
from copy               import deepcopy
from bokeh.document     import Document
from bokeh.models       import Widget, Button
from view.fonticon      import FontIcon
from utils              import initdefaults, dataclass, dflt
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

@dataclass
class TaskDescriptor:
    "Access to a task"
    _LABEL = '%({self.attrname}){self.fmt}'
    __NONE = type('_None', (), {})
    label: str                = ""
    fmt  : str                = ""
    keys : List[str]          = dflt([])
    fget : Optional[Callable] = None
    fset : Optional[Callable] = None
    attrname : str            = ""
    def __post_init__(self):
        if not self.fmt:
            ix1, ix2    = self.label.rfind("%("), self.label.rfind(")")
            self.fmt   = self.label[ix2+1:]
            self.keys  = self.label[ix1+2:ix2].split(".")
            self.label = self.label[:ix1].strip()

        if isinstance(self.keys, str):
            self.keys = self.keys.split('.')
        assert len(self.keys) >= 2
        assert len(self.fmt)
        assert len(self.label)

    def __set_name__(self, _, name):
        self.attrname = name

    def __model(self, obj):
        # pylint: disable=protected-access
        return getattr(obj._model, self.keys[0]) # pylint: disable=protected-access

    def get(self, obj, wherefrom = "default"):
        """
        Gets the attribute in the task.

        Use config = True to access the default value
        """
        mdl = self.__model(obj)
        mdl = (getattr(mdl, 'task', mdl) if wherefrom == "model"  else
               mdl.configtask            if wherefrom == "config" else
               mdl.defaultconfigtask)

        for key in self.keys[1:]:
            mdl = getattr(mdl, key)
        # pylint: disable=not-callable
        return self.fget(mdl) if callable(self.fget) else mdl

    getdefault = get

    def __get__(self, obj, tpe):
        return self if obj is None else self.get(obj, 'model')

    def __set__(self, obj, val):
        tsk  = self.__model(obj).task
        outp = obj._get_output() # pylint: disable=protected-access
        if len(self.keys) == 2:
            # pylint: disable=not-callable
            val = self.fset(tsk, val) if callable(self.fset) else val
            outp.setdefault(self.keys[0], {})[self.keys[1]] = val
        else:
            mdl = outp.setdefault(self.keys[0], {}).get(self.keys[1], self.__NONE)
            if mdl is self.__NONE:
                mdl = deepcopy(getattr(tsk, self.keys[1]))
                outp[self.keys[0]][self.keys[1]] = mdl

            for key in self.keys[2:-1]:
                mdl = getattr(mdl, key)

            if callable(self.fset):
                # pylint: disable=not-callable
                setattr(mdl, self.keys[-1], self.fset(mdl, val))
            else:
                setattr(mdl, self.keys[-1], val)

    def line(self) -> Tuple[str, str]:
        "return the line for this descriptor"
        return self.label, self._LABEL.format(self = self)

    @classmethod
    def attr(cls, akeys:str, fget = None, fset = None):
        "sets a task's attribute"
        return cls(akeys, "", [], fget, fset) # type: ignore

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

        return cls(akeys, "", [], lambda i: i is not None, _fset) # type: ignore

@dataclass
class AdvancedDescriptor:
    "class for facilitating the creation of descriptors"
    _LABEL  = '%({self.attrname}){self.fmt}'
    cnf:      str = ""
    label:    str = ""
    fmt:      str = ""
    ctrlname: str = ""
    attrname: str = ""
    ctrlgroup:str = "theme"
    def __post_init__(self):
        if isinstance(self.cnf, type):
            self.cnf = getattr(self.cnf, 'name')

        if self.fmt == "" and "%(" in self.label:
            ix1, ix2      = self.label.rfind("%("), self.label.rfind(")")
            self.ctrlname = self.label[ix1+2:ix2].strip()
            self.fmt      = self.label[ix2+1:].strip()
            self.label    = self.label[:ix1].strip()
        elif self.fmt == "" and "%" in self.label:
            ix1        = self.label.rfind("%")
            self.fmt   = self.label[ix1+1:].strip()
            self.label = self.label[:ix1].strip()
        assert self.cnf != ""
        assert len(self.fmt)
        assert len(self.label)
        if ":" in self.ctrlname:
            self.ctrlgroup, self.ctrlname = self.ctrlname.split(":")


    def __set_name__(self, _, name):
        assert name == self.attrname or not self.attrname
        self.attrname = name
        if not getattr(self, 'ctrlname'):
            self.ctrlname = name[1 if name[0] == '_' else 0:]

    def _controller(self, inst):
        return getattr(getattr(inst, '_ctrl'), self.ctrlgroup)

    def __get__(self, inst, _):
        if inst is None:
            return self
        out = self._controller(inst).get(self.cnf, self.ctrlname)
        return out

    def __set__(self, inst, value):
        return self._controller(inst).update(self.cnf, **{self.ctrlname: value})

    def getdefault(self, inst):
        "return the default value"
        out = self._controller(inst).get(self.cnf, self.ctrlname, defaultmodel = True)
        return out

    def line(self) -> Tuple[str, str]:
        "return the line for this descriptor"
        return self.label, self._LABEL.format(self = self)

@dataclass
class FigureSizeDescriptor(AdvancedDescriptor):
    "defines the figure height"
    label:    str = 'Plot height'
    fmt:      str = "d"
    ctrlname: str = "figsize"
    isheight      = cast(bool, property(lambda self: 'height' in self.attrname))
    def __set_name__(self, _, name):
        super().__set_name__(_, name)
        self.label = 'Plot '+ ("height" if self.isheight else "width")

    def __get__(self, inst, _):
        return self if inst is None else super().__get__(inst, _)[self.isheight]

    def __set__(self, inst, value):
        vals = list(super().__get__(inst, None))
        vals[self.isheight] = int(value)
        return super().__set__(inst, tuple(vals))

    def getdefault(self, inst):
        "return the default value"
        return super().getdefault(inst)[self.isheight]

@dataclass
class YAxisRangeDescriptor(AdvancedDescriptor):
    "defines the figure height"
    label:    str = 'Y-axis max'
    fmt:      str = ".4of"
    ctrlname: str = "ybounds"
    ctrlgroup:str = "display"
    isheight      = cast(bool, property(lambda self: 'max' in self.attrname))
    def __set_name__(self, _, name):
        super().__set_name__(_, name)
        self.label = 'Y axis'+ ("max" if self.isheight else "min")

    def __get__(self, inst, _):
        if inst is None:
            return self
        out = super().__get__(inst, _)[self.isheight]
        return out

    def __set__(self, inst, value):
        vals                = list(super().__get__(inst, None))
        vals[self.isheight] = None if value is None else float(value)
        return super().__set__(inst, tuple(vals))

    def getdefault(self, inst):
        "return the default value"
        return super().getdefault(inst)[self.isheight]

@dataclass
class ThemeNameDescriptor(AdvancedDescriptor):
    "defines the theme to use"
    _LABEL  = ('%({self.attrname}'
               +'|basic:basic'
               +'|dark:dark'
               +'|light_minimal:bokehlight'
               +'|dark_minimal:bokehdark'
               +'|caliber:caliber'
               +'){self.fmt}')

    fmt:      str = "c"
    label:    str = "Plot color theme"
    cnf:      str = "main"
    ctrlname: str = "themename"

class AdvancedWidget:
    "A button to access the modal dialog"
    __widget: Button
    __doc:    Document
    __action: type
    def __init__(self, ctrl, mdl = None):
        ctrl.theme.updatedefaults('keystroke', advanced = 'Alt-a')
        self._theme = ctrl.theme.add(AdvancedWidgetTheme(), False)
        self._ctrl  = ctrl
        self._model = mdl

    def _body(self) -> AdvancedWidgetBody:  # pylint: disable=no-self-use
        return ()

    def _title(self) -> str:                # pylint: disable=no-self-use
        return ""

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
            dfval, found = _default(keys)
            if not found or dfval == _value(keys):
                return title, '', val

            if '|' in val:
                opts = val[val.find('(')+1:val.find(')')]
                disp = dict(i.split(':') for i in opts.split('|')[1:])[str(dfval)]
            else:
                try:
                    disp = (' '  if dfval is None  else
                            '✓'  if dfval is True  else
                            '▢'  if dfval is False else
                            dfval if isinstance(dfval, str) else
                            ('%'+val[val.rfind(')')+1:]) % dfval)
                except TypeError:
                    disp = str(dfval)

            return title, f'({disp})', val

        bdy  = self._body()
        if len(bdy) and isinstance(bdy[0], AdvancedTab):
            for k in bdy:
                k.body = tuple(_add(i, j)  for i, j in k.body) # type: ignore
        else:
            bdy = tuple(_add(i, j)  for i, j in bdy) # type: ignore


        args = dict(title   = self._title(),
                    context = lambda title: self,
                    body    = bdy,
                    model   = model)
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

class AdvancedTaskWidget(AdvancedWidget):
    "Means for configuring tasks with a modal dialog"
    def __init__(self, ctrl, mdl):
        super().__init__(ctrl, mdl)
        self.__outp: Dict[str, Dict[str, Any]] = {}

    def __enter__(self):
        self.__outp.clear()
        super().__enter__()

    def __exit__(self, tpe, val, bkt):
        LOGS.debug("%s output => %s", self._title(), self.__outp)
        for key, elems in self.__outp.items():
            getattr(self._model, key).update(**elems)

        super().__exit__(tpe, val, bkt)

    def _get_output(self):
        return self.__outp

class TabCreator:
    "create tabs"
    def __call__(self, title: str, *args, **kwa):
        "adds descriptors to a class or returns an advanced tab"
        first     = next((i for i in args if isinstance(i, bool)), True)
        itms:list = []
        for i, j in enumerate(args):
            if isinstance(j, bool):
                continue
            label = f"{''.join(title.split()).lower()}{i}"
            if isinstance(j, str) and "%(" in j and '.' in j[j.rfind("%("):j.rfind(")")]:
                itms.append((label, self.taskattr(j)))
            else:
                itms.append((label, self.line(j))       if isinstance(j, str)   else
                            (label, self.taskattr(**j)) if isinstance(j, dict)  else
                            (label, self.line(*j))      if isinstance(j, tuple) else
                            (label, j))

        itms.extend(kwa.items())

        def _wrapper(cls):
            lst: list = deepcopy(itms)
            for i, j in lst:
                if hasattr(j, '__set_name__'):
                    j.__set_name__(cls, i)

            old = getattr(cls, '_body')
            def _body(self) -> AdvancedWidgetBody:
                cur  = old(self)
                mine = AdvancedTab(title, *(i.line() for _, i in lst))
                return (mine, *cur) if first else (*cur, mine)
            setattr(cls, '_body', _body)

            for i, j in lst:
                setattr(cls, i, j)
            return cls
        return _wrapper

    @classmethod
    def taskattr(cls, akeys:str, fget = None, fset = None):
        "sets a task's attribute"
        return TaskDescriptor.attr(akeys, fget, fset)

    @classmethod
    def tasknoneattr(cls, akeys:str):
        "sets a task's attribute to None or the default value"
        return TaskDescriptor.none(akeys)

    def figure(self, cnf, disp = None):
        "adds descriptors to a class or returns an advanced tab"
        return self("Theme",
                    _themename = ThemeNameDescriptor(),
                    _figwidth  = FigureSizeDescriptor(cnf),
                    _figheight = FigureSizeDescriptor(cnf),
                    _ymin      = YAxisRangeDescriptor(cnf if disp is None else disp),
                    _ymax      = YAxisRangeDescriptor(cnf if disp is None else disp))

    line      : type = AdvancedDescriptor
    widget    : type = AdvancedWidget
    taskwidget: type = AdvancedTaskWidget
    @staticmethod
    def title(title):
        "add a title"
        def _wrapper(cls):
            setattr(cls, '_title', lambda *_: title)
            return cls
        return _wrapper

tab = TabCreator() # pylint: disable=invalid-name
