#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"dealing with all widgets"
from typing       import List
from bokeh        import layouts
from bokeh.models import Widget
from ...model     import TasksModelController
from ._jobsstatus import JobsStatusBar
from ._plot       import PeakcallingPlotWidget
from ._explorer   import StorageExplorer
from ._exporter   import CSVExporter
from ._tasks      import TaskExplorer

class MasterWidget:
    "All widgets together"
    def __init__(self):
        self.status = JobsStatusBar()
        self.plot   = PeakcallingPlotWidget()
        self.cache  = StorageExplorer()
        self.tasks  = TaskExplorer()
        self.export = CSVExporter()
        self._ctrl  = TasksModelController()

    @property
    def _widgets(self):
        return self.tasks, self.plot, self.cache, self.export, self.status

    def swapmodels(self, ctrl):
        'swap models'
        for i in self._widgets:
            if hasattr(i, 'swapmodels'):
                i.swapmodels(ctrl)
        self._ctrl.swapmodels(ctrl)

    def reset(self, *_):
        "reset all"
        for i, j in self.__dict__.items():
            if i[0] != '_' and callable(getattr(j, 'reset', None)):
                j.reset(*_)

    def observe(self, ctrl):
        """observe the controller"""
        for i in self._widgets:
            if hasattr(i, 'observe'):
                i.observe(ctrl, self._ctrl)

    def addtodoc(self, mainview, ctrl, doc) -> List[layouts.WidgetBox]:
        "sets the items up"
        itms: List[Widget] = sum(
            (i.addtodoc(ctrl, doc) for i in self._widgets if i is not self.export),
            []
        )
        itms.extend(self.export.addtodoc(mainview, ctrl, doc))

        return [
            layouts.widgetbox(
                itms,
                width  = max(i.width    for i in itms),
                height = sum(i.height   for i in itms)
            )
        ]
