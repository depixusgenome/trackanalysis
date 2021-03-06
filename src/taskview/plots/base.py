#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from    typing                  import TypeVar
from    taskcontrol.modelaccess import PlotModelAccess
from    taskmodel.application   import TaskIOTheme
# pylint: disable=unused-import
from    view.plots.base         import (
    CACHE_TYPE, themed, checksizes, GroupStateDescriptor, PlotAttrsView,
    PlotThemeView, PlotUpdater, AxisOberver, PlotCreator,
    PlotView as _PlotView, PlotModelType, ControlModel, ControlModelType
)

ModelType = TypeVar('ModelType', bound = PlotModelAccess)
PlotType  = TypeVar('PlotType',  bound = PlotCreator)
ControlModel.register(PlotModelAccess)
class PlotView(_PlotView[PlotType]):
    "plot view"
    # pylint: disable=arguments-differ
    def _ismain(self, ctrl, tasks = None, ioopen = None, iosave = None):
        "Set-up things if this view is the main one"
        self._plotter.ismain(ctrl)
        cnf = ctrl.theme.model("tasks.io", True)
        if cnf is None:
            ctrl.theme.add(TaskIOTheme().setup(tasks, ioopen, iosave), False)
        else:
            diff = cnf.setup(tasks, ioopen, iosave).diff(cnf)
            if diff:
                ctrl.theme.updatedefaults(cnf, **diff)
