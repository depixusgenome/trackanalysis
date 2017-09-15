#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track class.

We add some methods and change the default behaviour:

    * Track:

        * *__init__* takes *path* as it's first positional argument
        * an *events* property is added
        * a *rawprecision* method is added
"""
import sys
from pathlib                import Path
from itertools              import product

from utils.decoration       import addto
from signalfilter           import PrecisionAlg

from ..                      import Track as _Track

Tasks     = sys.modules['app.__scripting__'].Tasks     # pylint: disable=invalid-name
scriptapp = sys.modules['app.__scripting__'].scriptapp # pylint: disable=invalid-name

class Track(_Track):
    "Adding helper functions for simple calls"
    def __init__(self, path = None, **kwa):
        cnf = scriptapp.control.getGlobal('css').last.path.trk
        if path in (Ellipsis, 'prev', ''):
            path = cnf.get()

        if path is None:
            path = scriptapp.trkdlg.open()
            if path is None:
                path = ''

        if isinstance(path, (tuple, str)):
            cnf.set(path)
            scriptapp.control.writeuserconfig()
        super().__init__(path = path, **kwa)

@addto(_Track)
def grfiles(self):
    "access to gr files"
    paths = scriptapp.grdlg.open()
    if paths is None or len(paths) == 0:
        return
    old = self.path
    self.__init__(path = ((old,) if isinstance(old, str) else old)+paths)

@addto(_Track)
def rawprecision(self, ibead):
    "the raw precision for a given bead"
    if isinstance(ibead, (tuple, list)):
        ibead = next(i for i in ibead if isinstance(i, int))
    return PrecisionAlg.rawprecision(self, ibead)

@addto(_Track)
def tasklist(self, *args, beadsonly = True):
    "creates a tasklist"
    return Tasks.get(self.path, *args, beadsonly = beadsonly)

@addto(_Track)
def processors(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    procs = Tasks.processors(self.path, *args, beadsonly = beadsonly)
    procs.data.setCacheDefault(0, self)
    procs.copy = copy
    return procs

@addto(_Track)
def apply(self, *args, copy = True, beadsonly = True):
    "returns an iterator over the result of provided tasks"
    return next(iter(self.processors(*args, beadsonly = beadsonly).run(copy = copy)))

def defaulttasklist(paths, upto):
    "Returns a default task list depending on the type of raw data"
    tasks = (Tasks.eventdetection, Tasks.peakselector)
    if isinstance(paths, (str, Path)) or len(paths) == 1:
        tasks = (Tasks.cleaning, Tasks.alignment)+tasks
    return (tasks if upto is None       else
            ()    if upto not in tasks  else
            tasks[:tasks.index(upto)+1])

@addto(_Track) # type: ignore
@property
def cleancycles(self):
    "returns cleaned cycles"
    return self.apply(*defaulttasklist(self.path, Tasks.alignment))[...,...]

@addto(_Track) # type: ignore
@property
def measures(self):
    "returns cleaned cycles for phase 5 only"
    phase = scriptapp.control.getGlobal('config').phase.measure.get()
    return self.cleancycles.withphases(phase)

def _addprop(name):
    fcn = getattr(_Track, name).fget
    setattr(Track, name, property(lambda self: fcn(self).withcopy()))

for tname in product(('beads', 'cycles'), ('only', '')):
    _addprop(''.join(tname))

__all__ = ['Track', 'defaulttasklist']
