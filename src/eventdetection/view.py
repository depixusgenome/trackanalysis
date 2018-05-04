#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing                  import TypeVar, Tuple
from    bokeh.models            import CheckboxGroup, RadioButtonGroup

from    view.plots              import GroupWidget
from    control.modelaccess     import PlotModelAccess
from    .processor              import AlignmentTactic

ModelType = TypeVar('ModelType', bound = PlotModelAccess)
class AlignmentWidget(GroupWidget[ModelType]):
    "Allows aligning the cycles on a given phase"
    INPUT   = RadioButtonGroup
    __ORDER = (None, AlignmentTactic.pull, AlignmentTactic.onlyinitial,
               AlignmentTactic.onlypull)
    def __init__(self, model:ModelType) -> None:
        super().__init__(model)
        self.css.title.alignment.labels.default = [u'ø', u'best', u'Φ1', u'Φ3']
        self.css.title.alignment.default        = u'Alignment'

    @staticmethod
    def observe(_):
        "do nothing"

    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        self._model.alignment.update(disabled = value == 0,
                                     **({'phase': self.__ORDER[value]} if value else {}))

    def _data(self):
        val    = getattr(self._model.alignment.task, 'phase', None)
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

class EventDetectionWidget(GroupWidget[ModelType]):
    "Allows displaying only events"
    INPUT = CheckboxGroup
    def __init__(self, model:ModelType) -> None:
        super().__init__(model)
        self.css.title.eventdetection.labels.default = [u'Find events']

    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        task = self._model.eventdetection.task
        if 0 in value and task is None:
            self._model.eventdetection.update()
        elif 0 not in value and task is not None:
            self._model.eventdetection.remove()

    @staticmethod
    def observe(_):
        "do nothing"

    def _data(self) -> dict:
        task = getattr(self._model, 'eventdetection').task
        return dict(active = [] if task is None else [0])
