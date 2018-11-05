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
setupdefaulttask(ClippingTask, picotwist = {'disabled': True}, sdi = {'disabled': False})
