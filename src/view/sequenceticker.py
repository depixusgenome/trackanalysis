#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Create a grid displaying a sequence"
from typing         import Optional, Tuple      # pylint: disable=unused-import

import  bokeh.core.properties as props
from    bokeh.models    import (LinearAxis,      # pylint: disable=unused-import
                                Model, ColumnDataSource, Range1d,
                                ContinuousTicker, BasicTicker, Ticker)

import  numpy   as np
import  sequences
from    .plotutils      import readsequence, checksizes, DpxHoverTool

class SequenceTicker(ContinuousTicker):
    "Generate ticks at fixed, explicitly supplied locations."
    major      = props.Dict(props.String, props.Seq(props.Float), default = {'': []})
    minor      = props.Dict(props.String, props.Seq(props.Float), default = {'': []})
    key        = props.String(default = '')
    usedefault = props.Bool(default = True)
    base       = props.Instance(Ticker, default = BasicTicker())

    __implementation__ = """
        import {ContinuousTicker} from "models/tickers/continuous_ticker"
        import *             as p from "core/properties"

        export class SequenceTicker extends ContinuousTicker
            type: 'SequenceTicker'

            @define {
                major:      [ p.Any, {} ]
                minor:      [ p.Any, {} ]
                key:        [ p.String, '']
                usedefault: [ p.Bool,     true]
                base:       [ p.Instance, null]
            }

            get_ticks_no_defaults: (data_low, data_high, desired_n_ticks) ->
                if @usedefault
                    return @base.get_ticks_no_defaults(data_low, data_high,
                                                       desired_n_ticks)
                return {
                    major: @major[@key]
                    minor: @minor[@key]
                }
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__defaults = dict() # type: Any
        self.__withbase = []     # type: Any
        self.__axis     = None   # type: Optional[SequenceTicker]
        self.__model    = None   # type: Any
        self.__fig      = None   # type: Any

    def getaxis(self):
        u"returns the fixed axis"
        return self.__axis

    def create(self, fig, mdl, cnf):
        "Sets the ticks according to the configuration"
        self.__model = mdl
        self.__fig   = fig
        if fig.ygrid[0].minor_grid_line_color is None:
            # bokehjs will never draw minor lines unless the color is
            # is set at startup
            fig.ygrid[0].minor_grid_line_color = 'navy'
            fig.ygrid[0].minor_grid_line_alpha = 0.

        order  = tuple('grid_line_'+i for i in ('color', 'width', 'dash', 'alpha'))
        order += tuple('minor_'+i for i in order)  # type: ignore
        order += 'y_range_name',                   # type: ignore
        self.__defaults = {i: getattr(fig.ygrid[0], i) for i in order}

        self.__withbase = dict()
        for name in ('color', 'dash', 'width', 'alpha'):
            gridprops = cnf.css['grid'+name].get()
            self.__withbase['grid_line_'+name]       = gridprops[0]
            self.__withbase['minor_grid_line_'+name] = gridprops[1]

        fig.extra_y_ranges        = {"bases": Range1d(start = 0., end = 1.)}
        fig.ygrid[0].ticker       = self
        fig.ygrid[0].y_range_name = 'bases'

        if self.__axis is None:
            self.__axis = type(self)()

        fig.add_layout(LinearAxis(y_range_name = "bases",
                                  axis_label   = cnf.css.yrightlabel.get(),
                                  ticker       = self.__axis),
                       'right')

        cnf.configroot.observe(('oligos', 'last.path.fasta'), self.reset)

    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return dict(gridcolor = ('lightblue', 'lightgreen'),
                    gridwidth = (2,           2),
                    gridalpha = (1.,          1.),
                    griddash  = ('solid',     'solid'))

    def reset(self):
        "Updates the ticks according to the configuration"
        mdl = self.__model
        fig = self.__fig
        key                    = mdl.sequencekey if len(mdl.oligos) else None
        self.usedefault        = True
        self.__axis.usedefault = True
        if key is not None:
            majors = {}
            minors = {}
            for name, seq in readsequence(mdl.sequencepath).items():
                peaks        = sequences.peaks(seq, mdl.oligos)
                majors[name] = tuple(peaks['position'][peaks['orientation']])
                minors[name] = tuple(peaks['position'][~peaks['orientation']])

            self.update(major = majors, minor = minors, key = key)
            self.__axis.update(major = {i: majors[i]+minors[i] for i in majors},
                               minor = dict.fromkeys(majors.keys(), tuple()),
                               key   = key)
            self.usedefault        = False
            self.__axis.usedefault = False

        info = self.__defaults if self.usedefault else self.__withbase
        for name in ('color', 'dash', 'width', 'alpha'):
            setattr(fig.ygrid[0], 'grid_line_'+name, info['grid_line_'+name])
            setattr(fig.ygrid[0], 'minor_grid_line_'+name, info['minor_grid_line_'+name])

class SequenceHoverMixin:
    "controls keypress actions"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__source = ColumnDataSource()
        self.__tool   = None # type: Optional[DpxHoverTool]
        self.model  = None # type: Any
        self.__size   = None # type: Any

    @staticmethod
    def impl(name, atts):
        "returns the coffeescript implementation"
        return """
                import * as p  from "core/properties"
                import {Model} from "model"

                export class %sView
                export class %s extends Model
                    default_view: %sView
                    type:"%s"

                    setsource: (source, values) ->
                        if values[0] == @_values[0] && values[1] == @_values[1]
                            return
                        if values[0] != @bias || values[1] != @stretch
                            return

                        tmp = source.data["values"]
                        source.data["z"] = tmp.map(((x)-> x*@stretch+@bias), @)
                        @_values = values
                        source.trigger('change:data')

                    @define {
                        %s
                        framerate : [p.Number, 1],
                        stretch   : [p.Number, 0],
                        bias      : [p.Number, 0]
                    }

                    @internal {
                        _values: [p.Array, [0, 1]]
                    }
                """ % ((name,)*4, atts)
    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return { 'hist.tooltips.radius': 1.,
                 'hist.tooltips'       : u'@z{1.1111} ↔ @values: @text'}

    @checksizes
    def __data(self):
        mdl   = self.model
        key   = mdl.sequencekey
        oligs = mdl.oligos
        osiz  = max((len(i) for i in oligs), default = self.__size.get())
        dseq  = readsequence(mdl.sequencepath)
        if len(dseq) == 0:
            return dict(values = [0], inds = [0], text = [''], z = [0])

        nbases = max(len(i) for i in dseq.values())
        data   = dict(values = np.arange(osiz, nbases+osiz),
                      inds   = np.full((nbases,), 0.5, dtype = 'f4'))
        for name, seq in dseq.items():
            seq        = sequences.marksequence(seq, oligs)
            data[name] = np.full((nbases,), ' ', dtype = 'U%d' % osiz)
            data[name][:len(seq)-osiz+1] = [seq[i:i+osiz] for i in range(len(seq)-osiz+1)]

        data['text'] = data.get(key, data[next(iter(dseq))])
        data['z']    = data['values']*mdl.stretch+(0. if mdl.bias is None else mdl.bias)
        return data

    def create(self, fig, mdl, cnf):
        "Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = mdl.bias,
                    stretch   = mdl.stretch)

        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return
        self.model         = mdl
        self.__tool        = hover[0]
        self.__size        = cnf.configroot.oligos.size
        self.__source.data = self.__data()

        rend          = fig.circle(x                = 'inds',
                                   y                = 'values',
                                   source           = self.__source,
                                   radius           = cnf.css.tooltips.radius.get(),
                                   radius_dimension = 'y',
                                   line_alpha       = 0.,
                                   fill_alpha       = 0.,
                                   x_range_name     = 'cycles',
                                   y_range_name     = 'bases',
                                   visible          = False)
        self.__tool.update(tooltips  = cnf.css.tooltips.get(),
                           mode      = 'hline',
                           renderers = rend)
        return self.__source

    def resetsource(self):
        "updates the tooltips for a new file"
        if self.__tool is None:
            return

        self.__source.data = self.__data()

    def reset(self, **kwa):
        "updates the tooltips for a new file"
        self.resetsource()
        kwa.setdefault('framerate', getattr(self.model.track, 'framerate', 1./30.))
        kwa.setdefault('bias',      self.model.bias)
        kwa.setdefault('stretch',   self.model.stretch)
        self.update(**kwa)
