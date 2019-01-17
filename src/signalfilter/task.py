#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from taskmodel import DataFunctorTask, Level
from .         import ForwardBackwardFilter, NonLinearFilter

class ForwardBackwardFilterTask(DataFunctorTask, ForwardBackwardFilter):
    u"Filters time series using the forward-backward algorithm"
    level = Level.none

class NonLinearFilterTask(DataFunctorTask, NonLinearFilter):
    u"Filters time series using the forward-backward algorithm"
    level = Level.none
