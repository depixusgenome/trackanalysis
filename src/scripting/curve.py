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

    def __mul__(self, plot):
        return plot.__rmul__(self)

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
    """
    Adds a curve to the plot.

    Example code:

        # adding a blue line on the left axis
        curve(data, color = 'blue', **bokeh_kwargs)
        # adding a (default) red line on the right axis
        curve(data, axis = 'y', **bokeh_kwargs)

    Specifying axis allows displaying a right (='y') or top (='x') axis.
    """
    def __init__(self, data, **kwa):
        self.data = data
        self.kwa  = kwa
        if 'color' in kwa:
            self.kwa['line_color'] = self.kwa.pop('color')

        axis = self.kwa.pop('axis', None)
        if axis is not None:
            self.kwa.setdefault(axis+'_range_name', 'right' if axis == 'y' else 'top')

        if 'y_range_name' in self.kwa and 'line_color' not in self.kwa:
            self.kwa['line_color'] = 'red'

        elif 'x_range_name' in self.kwa and 'line_color' not in self.kwa:
            self.kwa['line_color'] = 'gray'

    def _action(self, plot):
        for axis in 'x', 'y':
            name = axis+'_range_name'
            rng  = getattr(plot, 'extra_{}_ranges'.format(axis))
            if name in self.kwa and self.kwa[name] not in rng:
                plot = plot*ExtraAxis(self.kwa[name], axis)

        rend  = plot.line(np.arange(len(self.data)), self.data, **self.kwa)
        found = False
        for axis in 'x', 'y':
            name = axis+'_range_name'
            if name in self.kwa:
                rng = getattr(plot, 'extra_{}_ranges'.format(axis))[self.kwa[name]]
                rng.renderers = list(rng.renderers)+[rend]
                found = True

        if not found:
            if len(plot.extra_x_ranges):
                plot.x_range.renderers = list(plot.x_range.renderers)+[rend]
            if len(plot.extra_y_ranges):
                plot.y_range.renderers = list(plot.y_range.renderers)+[rend]
        return plot

def show():
    "shows the plot"
    return Show()

def curve(*args, **kwa):
    "adds a curve"
    return Curve(*args, **kwa)

def rcurve(*args, axis = 'y', **kwa):
    "adds a curve"
    return Curve(*args, axis = axis, **kwa)

def extra(*args, **kwa):
    "adds a right axis"
    return ExtraAxis(*args, **kwa)
