#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Used for scripting: something similar to matplotlib's pyplot.

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
# pylint: disable=unused-import,invalid-name
from typing                 import cast
from copy                   import copy as shallowcopy, deepcopy
from functools              import wraps
from enum                   import Enum
import inspect

import numpy                as np
try:
    import matplotlib.pyplot as plt     # pylint: disable=import-error
except ImportError:
    pass
try:
    import bokeh                        # pylint: disable=import-error
except ImportError:
    pass
import pandas               as pd

from utils                  import updatedeepcopy
from model.task             import *  # pylint: disable=wildcard-import
import control.processor
from control.globalscontrol import GlobalsController
from control.taskcontrol    import create as _create
from cordrift.processor     import DriftTask
from view.globalsview       import View, GlobalsView
from view.dialog            import FileDialog
from app                    import Defaults

from data                       import Track as _Track, Beads, Cycles
from eventdetection.processor   import ExtremumAlignmentTask, EventDetectionTask
from eventdetection.data        import Events
from signalfilter               import (PrecisionAlg, RollingFilter, NonLinearFilter,
                                        ForwardBackwardFilter)
from peakfinding.processor      import PeakSelectorTask
from peakcalling.processor      import FitToHairpinTask

from .curve                 import * # pylint: disable=wildcard-import

_frame = None
for _frame in inspect.stack()[1:]:
    if 'importlib' not in _frame.filename:
        assert (_frame.filename == '<stdin>'
                or _frame.filename.startswith('<ipython'))
    break
del _frame

class ScriptingView(View):
    "Dummy view for scripting"
    APPNAME = 'Scripting'
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.trkdlg  = FileDialog(filetypes = 'trk|*',
                                  config    = self._ctrl,
                                  multiple  = False,
                                  title     = "open a track file")

        self.grdlg   = FileDialog(filetypes = 'gr|*',
                                  config    = self._ctrl,
                                  multiple  = True,
                                  title     = "open a gr files")

        cnf = self._ctrl.getGlobal("config").tasks
        cnf.defaults = dict(selection      = DataSelectionTask(),
                            alignment      = ExtremumAlignmentTask(),
                            driftperbead   = DriftTask(onbeads = True),
                            driftpercycle  = DriftTask(onbeads = False),
                            cycles         = CycleCreatorTask(),
                            eventdetection = EventDetectionTask(),
                            peakselector   = PeakSelectorTask(),
                            fittohairpin   = FitToHairpinTask())

    @property
    def control(self):
        "returns the controller"
        return self._ctrl

scriptapp = Defaults.application(main = ScriptingView)() # pylint: disable=no-member

class Tasks(Enum):
    "possible tasks"
    selection      = 'selection'
    alignment      = 'alignment'
    driftperbead   = 'driftperbead'
    driftpercycle  = 'driftpercycle'
    cycles         = 'cycles'
    eventdetection = 'eventdetection'
    peakselector   = 'peakselector'
    fittohairpin   = 'fittohairpin'

    def __call__(self, **kwa):
        cnf = scriptapp.control.getGlobal("config").tasks
        return updatedeepcopy(cnf[self.value].get(), **kwa)

    @classmethod
    def get(cls, arg, **kwa):
        "returns the task associated to the argument"
        if isinstance(arg, (str, cls)):
            return cls(arg)(**kwa)

        elif isinstance(arg, tuple):
            return cls(arg[0])(**arg[1], **kwa)

        else:
            assert isinstance(arg, Task)
            if len(kwa):
                return updatedeepcopy(arg, **kwa)
            return arg

class Track(_Track):
    "Adding helper functions for simple calls"
    def __init__(self, path = None, **kwa):
        if path is None:
            path = scriptapp.trkdlg.open()
            if path is None:
                path = ''
        else:
            scriptapp.control.getGlobal('config').last.path.trk.set(path)
            scriptapp.control.writeconfig()
        super().__init__(path = path, **kwa)

    def grfiles(self):
        "access to gr files"
        paths = scriptapp.grdlg.open()
        if paths is None or len(paths) == 0:
            return
        old = self.path
        self.__init__(path = ((old,) if isinstance(old, str) else old)+paths)

    def rawprecision(self, ibead):
        "the raw precision for a given bead"
        if isinstance(ibead, (tuple, list)):
            ibead = next(i for i in ibead if isinstance(i, int))
        return PrecisionAlg.rawprecision(self, ibead)

    def tasklist(self, *args, beadsonly = True):
        "creates a tasklist"
        return ([TrackReaderTask(path = self.path, beadsonly = beadsonly)]
                + [Tasks.get(i) for i in args])

    def apply(self, *args, copy = True, beadsonly = True):
        "returns an iterator over the result of provided tasks"
        procs = _create(self.tasklist(*args, beadsonly = beadsonly))
        procs.data.setCacheDefault(0, self)
        return next(iter(procs.run(copy = copy)))

    @property
    def measures(self):
        "returns cycles for phase 5 only"
        phase = scriptapp.control.getGlobal('config').phase.measure.get()
        return self.cycles.withphases(phase)

    @property
    def events(self) -> Events:
        "returns events in phase 5 only"
        phase = scriptapp.control.getGlobal('config').phase.measure.get()
        return Events(track = self, beadsonly = True,
                      first = phase, last = phase,
                      parents= (self.path,))

def _copied(fcn):
    @wraps(fcn)
    def _fcn(self, *args, __old__ = fcn, **kwargs):
        stack = inspect.stack()
        if len(stack) > 1 and stack[1].filename.endswith('trackitems.py'):
            cpy = self
        else:
            cpy = shallowcopy(self)
        __old__(cpy, *args, **kwargs)
        return cpy
    _fcn.__old__ = fcn
    return _fcn

for _cls in (Beads, Cycles, Events):
    _cls._COPY = True # pylint: disable=protected-access
    _cls.rawprecision = lambda self, ibead: self.track.rawprecision(ibead)
    for itm in inspect.getmembers(_cls, callable):
        if itm[0].startswith('with'):
            setattr(_cls, itm[0], _copied(itm[1]))

def _withfilter(self, tpe = NonLinearFilter, **kwa):
    "applies the filter to the data"
    filt = tpe(**kwa)
    fcn  = lambda info: (info[0],
                         filt(info[1], precision = self.track.rawprecision(info[0])))
    return self.withaction(fcn)

for _cls in (Beads, Cycles, Events):
    _cls.withfilter   = _withfilter

del _cls
del _copied
del _withfilter
