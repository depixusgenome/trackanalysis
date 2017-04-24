#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"for speeding up the creation of figures"
from itertools      import chain
import numpy as np
from bokeh.plotting import Figure, figure
from bokeh.io       import show as _show
from bokeh.models   import DataRange1d, LinearAxis, ColumnDataSource

from data           import TrackItems
from utils          import EVENTS_DTYPE

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
        _show(plot)

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
    def __init__(self, *data, bias = 0., stretch = 1., positions = None, **kwa):
        self.data    = data[0] if len(data) == 1 else data
        self.kwa     = kwa
        self.bias    = bias
        self.stretch = stretch
        self.pos     = positions
        if 'line_color' in kwa:
            self.kwa['color'] = self.kwa.pop('line_color')

        axis = self.kwa.pop('axis', None)
        if axis is not None:
            self.kwa.setdefault(axis+'_range_name', 'right' if axis == 'y' else 'top')

        if 'y_range_name' in self.kwa and 'color' not in self.kwa:
            self.kwa['color'] = 'red'

        elif 'x_range_name' in self.kwa and 'color' not in self.kwa:
            self.kwa['color'] = 'gray'

    def __render(self, plot):
        kwa   = dict(self.kwa)
        glyph = kwa.pop('glyph', 'line')
        if glyph == 'line' and 'color' in kwa:
            kwa['line_color'] = kwa.pop('color')
        return lambda *x, **y: getattr(plot, glyph)(*x, **y, **kwa)

    def __iterdata(self):
        if isinstance(self.data, TrackItems):
            yield from (i for _, i in self.data)
        elif isinstance(self.data, dict):
            yield from self.data.values()
        elif np.isscalar(self.data[0]):
            yield self.data
        else:
            yield from self.data

    def __axes(self, plot):
        ranges = []
        for axis in 'x', 'y':
            name = axis+'_range_name'
            rng  = getattr(plot, 'extra_{}_ranges'.format(axis))
            if name in self.kwa:
                if self.kwa[name] not in rng:
                    plot = plot*ExtraAxis(self.kwa[name], axis)
                ranges.append(rng[self.kwa[name]])
            else:
                ranges.append(getattr(plot, axis+'_range'))
        return ranges

    def _arrays(self, lens):
        data = np.full ((sum(lens),), np.NaN, dtype = 'f4')
        time = np.empty((len(data),),         dtype = 'f4')
        pos  = self.pos
        if pos is None:
            pos = np.arange(max(lens), dtype = 'f4')
        return self.bias + self.stretch*pos, data, time

    def source(self, source = None):
        "returns a columndatasource"
        vals = list(self.__iterdata())
        if vals[0].dtype == EVENTS_DTYPE:
            vals = np.concatenate(vals)
        else:
            vals = [(0, i) for i in vals]

        lens             = [len(j)+1 for _, j in vals]
        pos, data, time  = self._arrays(lens)
        for i, (start, j) in zip(chain([0], np.cumsum(lens)), vals):
            data[i:i+len(j)] = j
            time[i:i+len(j)] = (start*self.stretch+self.bias) + pos[:len(j)]

        if source is None:
            return ColumnDataSource(data = {'z': data, 't': time})
        else:
            source.data = {'z': data, 't': time}
            return source

    def plot(self, plot, source):
        "plots a source"
        axes     = self.__axes(plot)
        renderer = self.__render(plot)
        rend     = renderer('t', 'z', source = source)
        for axis in axes:
            axis.renderers = list(axis.renderers)+[rend]
        return plot

    def _action(self, plot):
        self.plot(plot, self.source())

def show(*args):
    "shows the plot"
    if len(args):
        _show(*args)
    else:
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
