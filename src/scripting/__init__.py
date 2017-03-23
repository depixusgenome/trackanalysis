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
from copy                   import copy
from functools              import wraps
import inspect

from control.globalscontrol import GlobalsController
from view.globalsview       import View, GlobalsView
from view.dialog            import FileDialog
from app                    import Defaults

from data                   import Track as _Track, Beads, Cycles
from eventdetection.data    import Events
from signalfilter           import (PrecisionAlg, RollingFilter, NonLinearFilter,
                                    ForwardBackwardFilter)

import numpy                as np
import matplotlib.pyplot    as plt
import pandas               as pd

frame = msg = fname = None
for frame in inspect.stack()[1:]:
    fname = frame.filename
    if 'importlib' not in fname:
        msg = "Use directly in the interpreter or not at all"
        assert fname == '<stdin>' or fname.startswith('<ipython'), msg
    break
del fname
del frame
del msg

class ScriptingView(View):
    "Dummy view for scripting"
    APPNAME = 'Scripting'
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.trkdlg    = FileDialog(filetypes = 'trk|ana|*',
                                    config    = self._ctrl,
                                    title     = "open a track file")
    @property
    def control(self):
        "returns the controller"
        return self._ctrl

scriptapp = Defaults.application(main = ScriptingView)() # pylint: disable=no-member

class Track(_Track):
    "Adding helper functions for simple calls"
    def __init__(self, path = None, **kwa):
        if path is None:
            path = scriptapp.trkdlg.open()
        else:
            scriptapp.control.getGlobal('config').last.path.trk.set(path)
            scriptapp.control.writeconfig()
        super().__init__(path = path, **kwa)

    def rawprecision(self, ibead):
        "the raw precision for a given bead"
        if isinstance(ibead, (tuple, list)):
            ibead = next(i for i in ibead if isinstance(i, int))
        return PrecisionAlg.rawprecision(self, ibead)

    measures = cast(Cycles, property(lambda self: self.cycles.withphase(5)))
    events   = cast(Events, property(lambda self: Events(track     = self,
                                                         beadsonly = True,
                                                         first     = 5,
                                                         last      = 5,
                                                         parents   = (self.path,))))

def _copied(fcn):
    @wraps(fcn)
    def _fcn(self, *args, __old__ = fcn, **kwargs):
        stack = inspect.stack()
        if len(stack) > 1 and stack[1].filename.endswith('trackitems.py'):
            cpy = self
        else:
            cpy = copy(self)
        __old__(cpy, *args, **kwargs)
        return cpy
    _fcn.__old__ = fcn
    return _fcn

for cls in (Beads, Cycles, Events):
    cls._COPY = True # pylint: disable=protected-access
    cls.rawprecision = lambda self, ibead: self.track.rawprecision(ibead)
    for itm in inspect.getmembers(cls, callable):
        if itm[0].startswith('with'):
            setattr(cls, itm[0], _copied(itm[1]))

def withfilter(self, tpe = NonLinearFilter, **kwa):
    "applies the filter to the data"
    filt = tpe(**kwa)
    fcn  = lambda info: (info[0],
                         filt(info[1], precision = self.track.rawprecision(info[0])))
    return self.withaction(fcn)

for cls in (Beads, Cycles, Events):
    cls.withfilter   = withfilter

del cls
del _copied
del withfilter
