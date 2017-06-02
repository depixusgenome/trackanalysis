#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track class.

We add some methods and change the default behaviour:

    * Track:

        * *__init__* takes *path* as it's first positional argument
        * an *events* property is added
        * a *rawprecision* method is added

    * Beads, Cycles:

        * can filter their output using *withfilter*

    * Beads, Cycles, Events:

        * *withcopy(True)* is called in the *__init__* by default
        * a *rawprecision* method is added
        * *with...* methods return an updated copy
"""
from itertools              import product

from data                   import Track as _Track, Beads, Cycles
from signalfilter           import PrecisionAlg, NonLinearFilter
from control.taskcontrol    import create as _create
from model.task             import TrackReaderTask
from eventdetection.data    import Events

from .scriptapp             import scriptapp, Tasks

class Track(_Track):
    "Adding helper functions for simple calls"
    def __init__(self, path = None, **kwa):
        cnf = scriptapp.control.getGlobal('config').last.path.trk
        if path in (Ellipsis, 'prev', ''):
            path = cnf.get()

        if path is None:
            path = scriptapp.trkdlg.open()
            if path is None:
                path = ''

        if isinstance(path, (tuple, str)):
            cnf.set(path)
            scriptapp.control.writeconfig()
        super().__init__(path = path, **kwa)

def _totrack(fcn):
    setattr(_Track, getattr(fcn, 'fget', fcn).__name__, fcn)

@_totrack
def grfiles(self):
    "access to gr files"
    paths = scriptapp.grdlg.open()
    if paths is None or len(paths) == 0:
        return
    old = self.path
    self.__init__(path = ((old,) if isinstance(old, str) else old)+paths)

@_totrack
def rawprecision(self, ibead):
    "the raw precision for a given bead"
    if isinstance(ibead, (tuple, list)):
        ibead = next(i for i in ibead if isinstance(i, int))
    return PrecisionAlg.rawprecision(self, ibead)

@_totrack
def tasklist(self, *args, beadsonly = True):
    "creates a tasklist"
    return ([TrackReaderTask(path = self.path, beadsonly = beadsonly)]
            + [Tasks.get(i) for i in args])

@_totrack
def apply(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    procs = _create(self.tasklist(*args, beadsonly = beadsonly))
    procs.data.setCacheDefault(0, self)
    return next(iter(procs.run(copy = copy)))

@_totrack # type: ignore
@property
def measures(self):
    "returns cycles for phase 5 only"
    phase = scriptapp.control.getGlobal('config').phase.measure.get()
    return self.cycles.withphases(phase)

@_totrack # type: ignore
@property
def events(self) -> Events:
    "returns events in phase 5 only"
    phase = scriptapp.control.getGlobal('config').phase.measure.get()
    return Events(track   = self,  data = self.beadsonly,
                  first   = phase, last = phase,
                  parents = (self.path,))

def _addprop(name):
    fcn = getattr(_Track, name).fget
    setattr(Track, name, property(lambda self: fcn(self).withcopy()))

for tname in product(('beads', 'cycles'), ('only', '')):
    _addprop(''.join(tname))

def _withfilter(self, tpe = NonLinearFilter, **kwa):
    "applies the filter to the data"
    filt = tpe(**kwa)
    fcn  = lambda info: (info[0],
                         filt(info[1], precision = self.track.rawprecision(info[0])))
    return self.withaction(fcn)

for _cls in (Beads, Cycles, Events):
    _cls.withfilter = _withfilter

__all__ = ['Track']
