#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All widgets used for displaying multiple fovs"
from ._jobsstatus import (
    hairpinnames, JobsStatusBarConfig, JobsStatusBar, JobsHairpinSelectConfig,
    JobsHairpinSelect
)
from ._plot          import PeakcallingPlotConfig, PeakcallingPlotWidget
from ._exporter      import CSVExporter
from ._explorer      import StorageExplorerConfig, StorageExplorer
from ._beadselection import BeadsPlotSelector, StatsPlotSelector
from ._main          import MasterWidget
