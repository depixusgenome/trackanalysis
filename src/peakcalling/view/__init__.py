#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from   importlib import import_module
from ._beadsplot import BeadsScatterPlot
from ._statsplot import FoVStatsPlot
from ._main      import FoVPeakCallingView

# make sure all configs are loaded
for i in ('cleaning', 'eventdetection', 'peakfinding', 'peakcalling'):
    import_module(f'{i}.processor.__config__')
del i
del import_module
