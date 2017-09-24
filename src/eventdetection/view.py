#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing         import TypeVar
from    bokeh.models   import CheckboxGroup, RadioButtonGroup

from    view.plots     import GroupWidget, PlotModelAccess
from    .processor     import AlignmentTactic

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

    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        if value == 0:
            self._model.alignment.remove()
        else:
            self._model.alignment.update(phase = self.__ORDER[value])

    def _data(self):
        val    = getattr(self._model.alignment.task, 'phase', None)
        active = 0 if val is None else self.__ORDER.index(AlignmentTactic(val))
        return dict(active = active)

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

    def _data(self) -> dict:
        return dict(active = [] if self._model.eventdetection.task is None else [0])
