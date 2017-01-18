#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
import numpy
from model  import Task, Level
from .      import ForwardBackwardFilter, NonLinearFilter

class SignalFilterTask(Task):
    u"Filters time series"
    level = Level.none
    _COPY = True
    def __init__(self, **kwa):
        super().__init__(self, **kwa)
        for name in set(self.__dict__).intersection(set(kwa)):
            setattr(self, name, kwa.get(name))
        self.copy = kwa.get('copy', self._COPY) # type: bool

    def __processor__(self):
        cpy =  self.__class__.__bases__[1]()
        for name, val in self.__dict__.items():
            if hasattr(cpy, name):
                setattr(cpy, name, val)

        if self.copy:
            fcn = lambda val: cpy(numpy.copy(val))
        else:
            fcn = cpy
        return lambda dat: dat.withfunction(fcn, beadonly = True)

class ForwardBackwardFilterTask(SignalFilterTask, ForwardBackwardFilter):
    u"Filters time series using the forward-backward algorithm"

class NonLinearFilterTask(SignalFilterTask, NonLinearFilter):
    u"Filters time series using the forward-backward algorithm"
