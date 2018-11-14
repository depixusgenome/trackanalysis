#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default configurations for each task
"""
from model.task.application import setupdefaulttask
from .                      import (BeadSubtractionTask, DataCleaningTask,
                                    ClippingTask)
setupdefaulttask(BeadSubtractionTask)
setupdefaulttask(DataCleaningTask)
setupdefaulttask(ClippingTask,
                 picotwist = {'lowfactor': 6, 'highfactor': 1},
                 sdi       = {'lowfactor': 4, 'highfactor': 0})
