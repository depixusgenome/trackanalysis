#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"for speeding up the creation of figures"
from itertools      import chain
import numpy as np

from utils                  import EVENTS_DTYPE
import utils.warnings       #  pylint: disable=unused-import

from bokeh.io               import output_notebook
from bokeh.models.widgets   import Panel, Tabs # pylint: disable=unused-import
from bokeh.plotting         import Figure, figure
from bokeh.io               import show as _show
from bokeh.models           import DataRange1d, LinearAxis, ColumnDataSource

from data.views             import TrackView

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
        return (None*self)*plot

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
        self.data    = data[0] if len(data) == 1 else None if len(data) == 0 else data
        self.kwa     = kwa
        self.bias    = bias
        self.stretch = stretch
        self.pos     = positions
        assert self.data is not None or self.pos is not None
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
        if isinstance(self.data, TrackView):
            yield from (i for _, i in self.data)
        elif isinstance(self.data, dict):
            yield from self.data.values()
        elif np.isscalar(self.data):
            yield np.ones((len(self.pos),), dtype = 'f4')*self.data
        elif self.data is None:
            yield np.ones((len(self.pos),), dtype = 'f4')
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
                axname = self.kwa[name]
                if axname not in rng:
                    plot = plot*ExtraAxis(axname, axis)
                    rng  = getattr(plot, 'extra_{}_ranges'.format(axis))
                ranges.append(rng[axname])
            else:
                ranges.append(getattr(plot, axis+'_range'))
        return ranges

    def _arrays(self, lens):
        data = np.full ((sum(lens),), np.NaN, dtype = 'f4')
        time = np.empty((len(data),),         dtype = 'f4')
        pos  = self.pos
        if pos is None:
            pos = np.arange(max(lens), dtype = 'f4')
        return self.stretch*pos, data, time

    def source(self, source = None):
        "returns a columndatasource"
        vals = list(self.__iterdata())
        if getattr(vals[0], 'dtype', 'f') == EVENTS_DTYPE:
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

def curve(*data, bias = 0., stretch = 1., positions = None, **kwa):
    "adds a curve"
    return Curve(*data, bias = bias, stretch = stretch, positions = positions, **kwa)

def rcurve(*data, axis = 'y', bias = 0., stretch = 1., positions = None, **kwa):
    "adds a curve"
    return Curve(*data, axis = axis, bias = bias, stretch = stretch, positions = positions, **kwa)

def extra(*args, **kwa):
    "adds a right axis"
    return ExtraAxis(*args, **kwa)

__all__ = ['output_notebook', 'Panel', 'Tabs', 'Figure', 'figure',
           'show', 'curve', 'rcurve', 'extra']
