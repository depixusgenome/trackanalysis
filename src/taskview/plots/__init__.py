#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for dealing with the JS side of the view"
from view.plots.bokehext    import DpxKeyedRow, DpxHoverTool, DpxNumberFormatter
from view.plots.ploterror   import PlotError as _PlotError
from .base                  import (checksizes, PlotModelAccess, PlotCreator,
                                    PlotView, CACHE_TYPE, PlotAttrsView, themed)
from .tasks                 import TaskPlotCreator, PlotModelType, TaskPlotModelAccess

class PlotError(_PlotError):
    "deals with cleaning errors"
    def __init__(self, *args, **kwa):
        super().__init__(self, *args, **kwa)
        from cleaning.processor import DataCleaningException
        self._exceptions = DataCleaningException
