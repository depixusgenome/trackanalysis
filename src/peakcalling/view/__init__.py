#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from   importlib import import_module
from .beadsplot  import BeadsScatterPlot
from .statsplot  import FoVStatsPlot
from .bothplots  import FoVPeakCallingView

# make sure all configs are loaded
for i in ('cleaning', 'eventdetection', 'peakfinding', 'peakcalling'):
    import_module(f'{i}.processor.__config__')
del i
del import_module
