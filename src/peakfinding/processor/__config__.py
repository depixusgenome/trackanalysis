#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default configurations for each task
"""
from taskmodel.application  import setupdefaulttask
from .                      import (PeakCorrelationAlignmentTask, SingleStrandTask,
                                    BaselinePeakTask, PeakSelectorTask,
                                    BaselinePeakFilterTask, MinBiasPeakAlignmentTask)
setupdefaulttask(PeakCorrelationAlignmentTask)
setupdefaulttask(MinBiasPeakAlignmentTask)
setupdefaulttask(SingleStrandTask,
                 picotwist = {'disabled': True},
                 sdi       = {'disabled': False})
setupdefaulttask(BaselinePeakTask)
setupdefaulttask(BaselinePeakFilterTask)
setupdefaulttask(PeakSelectorTask,
                 picotwist = {'rawfactor': 2.0},
                 muwells   = {'rawfactor': 4.0},
                 sdi       = {'rawfactor': 1.0})
