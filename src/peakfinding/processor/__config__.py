#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default configurations for each task
"""
from model.task.application import setupdefaulttask
from .                      import (PeakCorrelationAlignmentTask, SingleStrandTask,
                                    PeakSelectorTask, MinBiasPeakAlignmentTask)
setupdefaulttask(PeakCorrelationAlignmentTask)
setupdefaulttask(MinBiasPeakAlignmentTask)
setupdefaulttask(SingleStrandTask,
                 picotwist = {'disabled': True},
                 sdi       = {'disabled': False})
setupdefaulttask(PeakSelectorTask,
                 picotwist = {'rawfactor': 2.0},
                 sdi       = {'rawfactor': 1.0})
