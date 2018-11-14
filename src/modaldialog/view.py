#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from copy               import deepcopy
from functools          import partial
from typing             import Dict, List, Tuple, Any, Union, cast
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
    label: str       = ""
    fmt  : str       = ""
    keys : List[str] = dflt([])
    attrname : str   = ""
    def __post_init__(self):
        if not self.fmt:
            ix1, ix2   = self.label.rfind("%("), self.label.rfind(")")
            self.fmt   = self.label[ix2+1:]
            self.keys  = self.label[ix1+2:ix2].split(".")
            self.label = self.label[:ix1].strip()

        if isinstance(self.keys, str):
            self.keys = self.keys.split('.')
        if self.keys[0] == 'task':
            self.keys = self.keys[1:]
        if len(self.keys) == 1:
            self.fmt = 'b'

        assert len(self.keys) >= 1
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

        if len(self.keys) == 1:
            return False if mdl is None else not mdl.disabled

        for key in self.keys[1:]:
            mdl = getattr(mdl, key)

        if self.fmt == 'b' and not isinstance(mdl, bool):
            return mdl is not None
        return mdl

    def getdefault(self, obj):
        """
        Gets the attribute in the task.

        Use config = True to access the default value
        """
        return self.get(obj)

    def __get__(self, obj, tpe):
        return self if obj is None else self.get(obj, 'model')

    def __set__(self, obj, val):
        outp = obj._get_output() # pylint: disable=protected-access
        if len(self.keys) == 1:
            outp.setdefault(self.keys[0], {})['disabled'] = not val
            return

        tsk = self.__model(obj).tasktype
        if len(self.keys) == 2:
            mdl = getattr(tsk, self.keys[1])
            if self.fmt == "b" and not isinstance(mdl, bool):
                val = deepcopy(mdl) if val else None
            outp.setdefault(self.keys[0], {})[self.keys[1]] = val
            return

        mdl = outp.setdefault(self.keys[0], {}).get(self.keys[1], self.__NONE)
        if mdl is self.__NONE:
            mdl = deepcopy(getattr(tsk, self.keys[1]))
            outp[self.keys[0]][self.keys[1]] = mdl

        for key in self.keys[2:-1]:
            mdl = getattr(mdl, key)

        attr = getattr(type(mdl)(), self.keys[-1])
        if self.fmt == "b" and not isinstance(attr, bool):
            val = deepcopy(attr) if val else None
        setattr(mdl, self.keys[-1], val)

    def line(self) -> Tuple[str, str]:
        "return the line for this descriptor"
        return self.label, self._LABEL.format(self = self)

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
        return self._controller(inst).get(self.cnf, self.ctrlname, defaultmodel = True)

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

    @staticmethod
    def onchangefiguresize(theme, doc, fig, old = None, **_):
        "on change figure size"
        if 'figsize' in old:
            @doc.add_next_tick_callback
            def _cb():
                fig.plot_width  = theme.figsize[0]
                fig.plot_height = theme.figsize[1]
                fig.trigger("sizing_mode", theme.figsize[-1], theme.figsize[-1])

    @classmethod
    def observe(cls, ctrl, theme, doc, fig):
        "applies the figure size changes"
        ctrl.theme.observe(theme, partial(cls.onchangefiguresize, theme, doc, fig))

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
        self.label = self.label.replace('max', "max" if self.isheight else "min")

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
class XAxisRangeDescriptor(YAxisRangeDescriptor):
    "defines the figure height"
    label:    str = 'X-axis max'
    ctrlname: str = "xbounds"

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

    @classmethod
    def observefigsize(cls, ctrl, theme, doc, fig):
        "applies the figure size changes"
        if any(isinstance(i, FigureSizeDescriptor) for i in cls.__dict__.values()):
            FigureSizeDescriptor.observe(ctrl, theme, doc, fig)

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

        def _format(label, val):
            if isinstance(val, bool):
                return '▢✓'[val]
            if isinstance(val, str):
                return val

            fmt = label[label.rfind("%")+1:]
            if ')' in fmt:
                fmt = label[label.rfind(')')+1:]
            if len(fmt) >= 2 and fmt[-2] == 'o':
                fmt = fmt[:-2]+fmt[-1]

            if fmt == 'b':
                return _format('', val is not None)
            if val is None:
                return ' '
            try:
                return ('%'+fmt) % val
            except TypeError:
                return str(val)

        def _add(title, val):
            keys        = val[val.rfind('%(')+2:val.rfind(')')].split('.')
            dfval, found = _default(keys)
            if not found or dfval == _value(keys):
                return title, '', val

            if '|' in val:
                opts = val[val.find('(')+1:val.find(')')]
                disp = dict(i.split(':') for i in opts.split('|')[1:])[str(dfval)]
            else:
                disp = _format(val, dfval)

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
        args      = sum((list(i.split('\n')) if isinstance(i, str) else [i] # type: ignore
                         for i in args), [])
        first     = next((i for i in args if isinstance(i, bool)), True)
        itms:list = []
        for i, j in enumerate(args):
            if isinstance(j, str):
                j = j.strip()
            if isinstance(j, bool) or not j:
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
    def taskattr(cls, akeys:str):
        "sets a task's attribute"
        return TaskDescriptor(akeys) # type: ignore

    def figure(self, cnf, disp = None, yaxis = True, xaxis = False, **kwa):
        "adds descriptors to a class or returns an advanced tab"
        if disp is None:
            if hasattr(cnf, 'display') and hasattr(cnf, 'theme'):
                cnf, disp = getattr(cnf, 'theme'), getattr(cnf, 'display')
            else:
                disp      = cnf
        args = [('_themename', ThemeNameDescriptor()),
                ('_figwidth',  FigureSizeDescriptor(cnf)),
                ('_figheight', FigureSizeDescriptor(cnf))]
        if xaxis:
            args += [('_xmin',  XAxisRangeDescriptor(disp)),
                     ('_xmax',  XAxisRangeDescriptor(disp))]
        if yaxis:
            args += [('_ymin',  YAxisRangeDescriptor(disp)),
                     ('_ymax',  YAxisRangeDescriptor(disp))]
        args += list(kwa.items())
        return self("Theme", **dict(args))

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
