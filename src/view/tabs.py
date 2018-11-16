#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from collections         import OrderedDict
from typing              import Dict, ClassVar, TypeVar, Tuple, Generic

from bokeh               import layouts
from bokeh.models        import Panel, Spacer, Tabs

from utils               import initdefaults
from utils.inspection    import templateattribute
from model.plots         import PlotState
from view.base           import BokehView

class TabsTheme:
    "Tabs Theme"
    name:    str            = "Tabs"
    initial: str            = ""
    width:   int            = 600
    height:  int            = 30
    titles:  Dict[str, str] = {}

    @initdefaults(locals())
    def __init__(self, **_):
        pass

TThemeType = TypeVar("TThemeType", bound = TabsTheme)
class TabsView(BokehView, Generic[TThemeType]):
    "A view with all plots"
    KEYS          : ClassVar[Dict[type, str]]
    TASKS_CLASSES : ClassVar[Tuple[type]]
    _tabs         : Tabs
    __theme       : TabsTheme
    def __init__(self, ctrl = None, **kwa):
        "Sets up the controller"
        super().__init__(ctrl = ctrl, **kwa)
        self.__theme = ctrl.theme.add(templateattribute(self, 0))
        self._panels = [cls(ctrl, **kwa) for cls in self.KEYS]

        for panel in self._panels:
            key                      = self.__key(panel)
            self.__theme.titles[key] = getattr(panel, 'PANEL_NAME', key.capitalize())

        cur = self.__select(self.__initial())
        for panel in self._panels:
            desc = type(panel.plotter).state
            desc.setdefault(panel.plotter, (PlotState.active if panel is cur else
                                            PlotState.disabled))

    def __initial(self):
        "return the initial tab"
        return next(i for i, j in self.KEYS.items() if j == self.__theme.initial)

    @classmethod
    def __key(cls, panel):
        return cls.KEYS[type(panel)]

    @staticmethod
    def __state(panel, val = None):
        if val is not None:
            panel.plotter.state = PlotState(val)
        return panel.plotter.state

    def __select(self, tpe):
        return next(i for i in self._panels if isinstance(i, tpe))

    def ismain(self, ctrl):
        "Allows setting-up stuff only when the view is the main one"
        for i in self.TASKS_CLASSES:
            self.__select(i).ismain(ctrl)
        ctrl.theme.updatedefaults("tasks.io", tasks = self.TASKS)
        if "advanced" in ctrl.display.model("keystroke", True):
            def _advanced():
                for panel in self._panels:
                    if self.__state(panel) is PlotState.active:
                        getattr(panel, 'advanced', lambda:None)()
                        break
            ctrl.display.updatedefaults('keystroke', advanced = _advanced)

    def __setstates(self):
        ind = next((i for i, j in enumerate(self._panels)
                    if self.__state(j) is PlotState.active),
                   None)
        if ind is None:
            cur = self.__initial()
            ind = next(i for i, j in enumerate(self._panels) if isinstance(i, cur))

        for panel in self._panels[:ind]:
            self.__state(panel, PlotState.disabled)
        self.__state(self._panels[ind], PlotState.active)
        for panel in self._panels[ind+1:]:
            self.__state(panel, PlotState.disabled)
        return ind

    def __createtabs(self, ind):
        panels = [Panel(title = self.__theme.titles[self.__key(i)],
                        child = Spacer(),
                        **self.defaultsizingmode())
                  for i in self._panels]
        return Tabs(tabs   = panels,
                    active = ind,
                    name   = self.NAME,
                    width  = self.__theme.width,
                    height = self.__theme.height)

    def addtodoc(self, ctrl, doc):
        "returns object root"
        super().addtodoc(ctrl, doc)
        tabs  = self.__createtabs(self.__setstates())

        roots = [None]*len(self._panels)
        def _root(ind):
            if roots[ind] is None:
                ret = self._panels[ind].addtodoc(ctrl, doc)
                while isinstance(ret, (tuple, list)) and len(ret) == 1:
                    ret = ret[0]
                if isinstance(ret, (tuple, list)):
                    ret  = layouts.column(ret, **self.defaultsizingmode())

                doc.add_next_tick_callback(lambda: self._panels[ind].plotter.reset(False))
                roots[ind] = ret
            return roots[ind]

        @ctrl.action
        def _py_cb(attr, old, new):
            self._panels[old].activate(False)
            self._panels[new].activate(True)
            ctrl.undos.handle('undoaction',
                              ctrl.emitpolicy.outastuple,
                              (lambda: setattr(tabs, 'active', old),))
            if roots[old] is not None:
                doc.remove_root(roots[old])
                doc.add_root(_root(new))

        tabs.on_change('active', _py_cb)

        def _fcn(**_):
            itm = next(i for i, j in enumerate(self._panels) if j.plotter.isactive())
            doc.add_root(_root(itm))

        if hasattr(ctrl, 'tasks'):
            ctrl.tasks.oneshot("opentrack", _fcn)
        else:
            ctrl.display.oneshot("applicationstarted", _fcn)

        mode = self.defaultsizingmode()
        return layouts.row(layouts.widgetbox(tabs, **mode), **mode)

    def observe(self, ctrl):
        "observing the controller"
        super().observe(ctrl)
        for panel in self._panels:
            panel.observe(ctrl)

def initsubclass(name, keys, tasksclasses = ()):
    "init TabsView subclass"
    def _fcn(lst):
        return tuple(j for i, j in enumerate(lst) if j not in lst[:i])
    def _wrapper(cls):
        cls.KEYS          = OrderedDict(keys)
        cls.TASKS_CLASSES = tuple(tasksclasses)
        cls.NAME          = name

        cls.TASKS = _fcn(sum((list(i.TASKS) for i in cls.TASKS_CLASSES), []))
        return cls
    return _wrapper
