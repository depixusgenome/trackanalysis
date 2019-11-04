#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default configurations for each task
"""
from taskmodel.application import setupdefaulttask
from taskmodel.track       import UndersamplingTask, RawPrecisionTask
from .                     import (
    BeadSubtractionTask, DataCleaningTask, ClippingTask, FixedBeadDetectionTask
)

setupdefaulttask(RawPrecisionTask)
setupdefaulttask(UndersamplingTask)
setupdefaulttask(BeadSubtractionTask)
setupdefaulttask(DataCleaningTask)
setupdefaulttask(FixedBeadDetectionTask)
setupdefaulttask(
    ClippingTask,
    picotwist = {'lowfactor': 6,  'highfactor': 1},
    muwells   = {'lowfactor': 6,  'highfactor': 1},
    sdi       = {'lowfactor': 4,  'highfactor': 0},
)
