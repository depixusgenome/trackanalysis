#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing                  import Tuple, List, TypeVar, Dict, Optional, Generic
from    bokeh.models            import (RadioButtonGroup, CheckboxGroup, Widget,
                                        Paragraph)

from    view.plots              import CACHE_TYPE
from    utils                   import initdefaults
from    utils.inspection        import templateattribute
from    .processor              import AlignmentTactic

ALIGN_LABELS: Dict[Optional[AlignmentTactic], str] = {
    None: 'ø',
    AlignmentTactic.pull: 'best',
    AlignmentTactic.onlyinitial: 'Φ1',
    AlignmentTactic.onlypull: 'Φ3'
}

class WidgetTheme:
    "WidgetTheme"
    name:   str       = "alignment"
    width:  int       = 100
    height: int       = 48
    labels: List[str] = list(ALIGN_LABELS.values())
    title:  str       = 'css:dpx-alignment-widget'

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass


ButtonT = TypeVar("ButtonT", RadioButtonGroup, CheckboxGroup)


class BaseWidget(Generic[ButtonT, ]):
    "Allows aligning the cycles on a given phase"
    __widget: ButtonT

    def __init__(self, ctrl, model, **kwa):
        name        = self.__class__.__name__.lower()
        self._theme = ctrl.theme.swapmodels(WidgetTheme(name = name, **kwa))
        self._task  = getattr(model, name.replace('widget', ''), model)

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        name          = self.__class__.__name__.replace("Widget", "")
        itm           = templateattribute(self, 0)
        self.__widget = itm(
            name   = f'Cycles:{name}',
            **{i: getattr(self._theme, i) for i in ('labels', 'width', 'height')},
            **self._data()
        )
        self.__widget.on_click(mainview.actionifactive(ctrl)(self._onclick_cb))

        if self._theme.title:
            if self._theme.title.startswith("css:"):
                self.__widget.css_classes = [self._theme.title[4:]]
                return [self.__widget]
            return [Paragraph(text = self._theme.title), self.__widget]
        return [self.__widget]

    @staticmethod
    def observe(_):
        "do nothing"

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
    __ORDER = tuple(ALIGN_LABELS)

    def _onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        self._task.update(phase = self.__ORDER[value], disabled = value == 0)

    def _data(self):
        val    = getattr(self._task.task, 'phase', None)
        active = 0 if val is None else self.__ORDER.index(AlignmentTactic(val))
        return dict(active = active)

class AlignmentModalDescriptor:
    "for use with modal dialogs"
    __ORDER = tuple(ALIGN_LABELS)
    __NAMES = tuple(ALIGN_LABELS.values())

    def __init__(self, *_):
        self._name = '_alignment'

    def __set_name__(self, _, name):
        self._name = name

    @classmethod
    def text(cls):
        "return the text for creating this line of menu"
        return "%({cls.__name__}:)"

    def line(self) -> Tuple[str, str]:
        "return the modal dialog line"
        vals = '|'.join(f'{i}:{j}' for i, j in enumerate(self.__NAMES))
        return ('Cycle alignment', f' %({self._name})|{vals}|')

    def getdefault(self,inst) -> int:
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
        if value:
            alignment.update(phase = self.__ORDER[value])
        else:
            alignment.update(disabled = True)

class EventDetectionWidget(BaseWidget[CheckboxGroup]):
    "Allows displaying only events"
    def __init__(self, ctrl, model):
        super().__init__(ctrl, model, labels = ['Find events'], title = None)

    def _onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        if 0 in value and self._task.task is None:
            self._task.update(disabled = False)
        elif 0 not in value and self._task.task is not None:
            self._task.update(disabled = True)

    def _data(self) -> dict:
        return dict(active = [] if self._task.task is None else [0])
