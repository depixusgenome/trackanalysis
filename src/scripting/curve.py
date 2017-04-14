#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"for speeding up the creation of figures"
import numpy as np
from bokeh.plotting import Figure, figure
from bokeh.io       import show as _show
from bokeh.models   import DataRange1d, LinearAxis

class Multiplier:
    "basic right multiplier"
    def __rmul__(self, plot):
        if plot is None:
            plot = figure()
        elif not isinstance(plot, Figure):
            plot = None*plot
        self._action(plot)
        return plot
    def _action(self, plot):
        raise NotImplementedError()

class Show(Multiplier):
    "shows the plot"
    def _action(self, plot):
        _show(plot)

    def __rmul__(self, plot):
        super().__rmul__(plot)
        return None

class ExtraAxis(Multiplier):
    "adds a right axis"
    def __init__(self, name = None, axis = 'y'):
        self.axis = axis
        self.name = ('right' if axis == 'y' else 'top') if name is None else name

    def _action(self, plot):
        setattr(plot, 'extra_{}_ranges'.format(self.axis), {self.name: DataRange1d()})
        plot.add_layout(LinearAxis(**{self.axis+'_range_name': self.name}),
                        'right' if self.axis == 'y' else 'top')
        return plot

class Curve(Multiplier):
    "adds a curve"
    def __init__(self, data, **kwa):
        self.data = data
        self.kwa  = kwa
        if 'color' in kwa:
            self.kwa['line_color'] = self.kwa.pop('color')

        if 'y_range_name' in kwa and 'line_color' not in self.kwa:
            self.kwa['line_color'] = 'red'

        elif 'x_range_name' in kwa and 'line_color' not in self.kwa:
            self.kwa['line_color'] = 'gray'

    def _action(self, plot):
        for axis in 'x', 'y':
            name = axis+'_range_name'
            rng  = getattr(plot, 'extra_{}_ranges'.format(axis))
            if name in self.kwa and self.kwa[name] not in rng:
                plot = plot*ExtraAxis(self.kwa[name], axis)

        rend = plot.line(np.arange(len(self.data)), self.data, **self.kwa)
        for axis in 'x', 'y':
            name = axis+'_range_name'
            if name in self.kwa:
                rng = getattr(plot, 'extra_{}_ranges'.format(axis))[self.kwa[name]]
                rng.renderers = list(rng.renderers)+[rend]
        return plot

class RightCurve(Curve):
    "A curve on the right axis"
    def __init__(self, data, **kwa):
        axis = kwa.pop('axis', 'y')
        kwa.setdefault(axis+'_range_name', 'right' if axis == 'y' else 'top')
        super().__init__(data, **kwa)

def show():
    "shows the plot"
    return Show()

def curve(*args, **kwa):
    "adds a curve"
    return Curve(*args, **kwa)

def rcurve(*args, **kwa):
    "adds a curve"
    return RightCurve(*args, **kwa)

def extra(*args, **kwa):
    "adds a right axis"
    return ExtraAxis(*args, **kwa)
