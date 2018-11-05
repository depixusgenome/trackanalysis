#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default configurations for each task
"""
from model.task.application import setupdefaulttask
from .processor             import RampAverageZTask, RampDataFrameTask
setupdefaulttask(RampAverageZTask)
setupdefaulttask(RampDataFrameTask)
