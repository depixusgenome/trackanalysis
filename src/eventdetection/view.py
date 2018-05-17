#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing                  import Tuple, List, TypeVar, Generic
from    bokeh.models            import (RadioButtonGroup, CheckboxGroup, Widget,
                                        Paragraph)

from    view.plots              import CACHE_TYPE
from    utils                   import initdefaults
from    utils.inspection        import templateattribute
from    .processor              import AlignmentTactic

class WidgetTheme:
    "tWidgetTheme"
    name   = "alignmentwidget"
    labels = ['ø', 'best', 'Φ1', 'Φ3']
    title  = 'Alignment'
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

T  = TypeVar("T", RadioButtonGroup, CheckboxGroup)
class BaseWidget(Generic[T]):
    "Allows aligning the cycles on a given phase"
    __widget: T
    def __init__(self, model, **kwa):
        name        = self.__class__.__name__.lower()
        self._theme = WidgetTheme(name = name, **kwa)
        self._task  = getattr(model, name.replace('widget', ''), model)

    def addtodoc(self, ctrl) -> List[Widget]:
        "creates the widget"
        name          = self.__class__.__name__.replace("Widget", "")
        itm           = templateattribute(self, 0)
        self.__widget = itm(labels = self._theme.labels, name = f'Cycles:{name}',
                            **self._data())
        self.__widget.on_click(ctrl.action(self._onclick_cb))

        if self._theme.title:
            return [Paragraph(text = self._theme.title), self.__widget]
        return [self.__widget]

    def observe(self, ctrl):
        "do nothing"
        self._theme = ctrl.theme.add(self._theme, True)

    def reset(self, cache:CACHE_TYPE):
        "resets the widget"
        cache[self.__widget].update(self._data())

    def _onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        raise NotImplementedError()

    def _data(self):
        raise NotImplementedError()

class AlignmentWidget(BaseWidget[RadioButtonGroup]):
    "Allows aligning the cycles on a given phase"
    __ORDER = (None, AlignmentTactic.pull, AlignmentTactic.onlyinitial,
               AlignmentTactic.onlypull)
    def _onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        self._task.update(phase = self.__ORDER[value], disabled = value == 0)

    def _data(self):
        val    = getattr(self._task.task, 'phase', None)
        active = 0 if val is None else self.__ORDER.index(AlignmentTactic(val))
        return dict(active = active)

class AlignmentModalDescriptor:
    "for use with modal dialogs"
    __ORDER = (None, AlignmentTactic.pull, AlignmentTactic.onlyinitial,
               AlignmentTactic.onlypull)
    __NAMES = 'ø','best', 'Φ1', 'Φ3'
    def __init__(self):
        self._name = '_alignment'

    def __set_name__(self, _, name):
        self._name = name

    def line(self) -> Tuple[str, str]:
        "return the modal dialog line"
        vals = '|'.join(f'{i}:{j}' for i, j in enumerate(self.__NAMES))
        return ('Cycle alignment', f' %({self._name}|{vals})c')

    def getdefault(self,inst)->int:
        "returns default peak finder"
        val = getattr(getattr(inst, '_model').alignment.defaultconfigtask, 'phase', None)
        return self.__ORDER.index(val)

    def __get__(self,inst,owner):
        if inst is None:
            return self
        val = getattr(getattr(inst, '_model').alignment.task, 'phase', None)
        return self.__ORDER.index(val)

    def __set__(self,inst,value):
        value     = int(value)
        alignment = getattr(inst, '_model').alignment
        if value == 0:
            alignment.remove()
        else:
            alignment.update(phase = self.__ORDER[value])

class EventDetectionWidgetTheme:
    "EventDetectionWidgetTheme"
    name   = "eventdetectionwidget"

class EventDetectionWidget(BaseWidget[CheckboxGroup]):
    "Allows displaying only events"
    def __init__(self, model):
        super().__init__(model, labels = ['Find events'], title = None)

    def _onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        if 0 in value and self._task.task is None:
            self._task.update(disabled = False)
        elif 0 not in value and self._task.task is not None:
            self._task.update(disabled = True)

    def _data(self) -> dict:
        return dict(active = [] if self._task.task is None else [0])
