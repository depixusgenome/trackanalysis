#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Create a grid displaying a sequence"
from    typing         import List, Optional, Tuple      # pylint: disable=unused-import
from    collections    import OrderedDict
from    pathlib        import Path
import  re
import  numpy   as np

import  bokeh.core.properties as props
from    bokeh.models    import (LinearAxis,      # pylint: disable=unused-import
                                Model, ColumnDataSource, Range1d,
                                ContinuousTicker, BasicTicker, Ticker,
                                Dropdown, Paragraph, AutocompleteInput,
                                CustomJS)

import  sequences

from    utils           import CachedIO

from   ..dialog         import FileDialog
from    .base           import checksizes, WidgetCreator
from    .bokehext       import DpxHoverTool, from_py_func

_CACHE = CachedIO(lambda path: OrderedDict(sequences.read(path)), size = 1)
def readsequence(path):
    "Reads / caches DNA sequences"
    if path is None or not Path(path).exists():
        return dict()
    try:
        return _CACHE(path)
    except: # pylint: disable=bare-except
        return dict()

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

    @property
    def axis(self):
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
        self.__source = None # type: Optional[ColumnDataSource]
        self.__tool   = None # type: Optional[DpxHoverTool]
        self.__size   = None # type: Any
        self.model    = None # type: Any

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
                        bias      : [p.Number, 0],
                        updating  : [p.String, ''],
                    }

                    @internal {
                        _values: [p.Array, [0, 1]]
                    }
                """ % (name, name, name, name, atts)

    @staticmethod
    def defaultconfig() -> dict:
        "default config"
        return { 'hist.tooltips.radius': 1.,
                 'hist.tooltips'       : u'@z{1.1111} ↔ @values: @text'}

    @property
    def source(self):
        "returns the tooltip source"
        return self.__source

    def create(self, fig, mdl, cnf):
        "Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = mdl.bias,
                    stretch   = mdl.stretch)

        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return
        self.model    = mdl
        self.__tool   = hover[0]
        self.__size   = cnf.configroot.oligos.size
        self.__source = ColumnDataSource(self.__data())

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

        src = self.__source
        fig = self._fig
        @from_py_func
        def _js_cb(src = src, fig = fig, cb_obj = None, window = None):
            if cb_obj.updating == '':
                return

            values = cb_obj.bias, cb_obj.stretch
            window.setTimeout(lambda a, b, c: a.setsrc(b, c), 500, cb_obj, src, values)
            bases       = fig.extra_y_ranges['bases']
            yrng        = fig.y_range
            bases.start = (yrng.start-cb_obj.bias)/cb_obj.stretch
            bases.end   = (yrng.end  -cb_obj.bias)/cb_obj.stretch

        self.js_on_change("updating", _js_cb)

    def reset(self, **kwa):
        "updates the tooltips for a new file"
        if self.__tool is None:
            return

        self.__source.data = self.__data()
        kwa.setdefault('framerate', getattr(self.model.track, 'framerate', 1./30.))
        kwa.setdefault('bias',      self.model.bias)
        kwa.setdefault('stretch',   self.model.stretch)
        self.update(**kwa)

    def slaveaxes(self, fig, src, extra:str, data:str, inpy = False):
        "slaves a histogram's axes to its y-axis"
        # pylint: disable=too-many-arguments,protected-access
        hvr = self
        def _onchangebounds(fig    = fig,
                            hvr    = hvr,
                            src    = src,
                            extra  = extra,
                            data   = data,
                            window = None):
            yrng = fig.y_range
            if hasattr(yrng, '_initial_start') and yrng.bounds is not None:
                yrng._initial_start = yrng.bounds[0]
                yrng._initial_end   = yrng.bounds[1]

            cycles = fig.extra_x_ranges[extra]
            frames = fig.x_range

            cycles.start = 0.
            frames.start = 0.

            bases        = fig.extra_y_ranges['bases']
            bases.start  = (yrng.start - hvr.bias)/hvr.stretch
            bases.end    = (yrng.end   - hvr.bias)/hvr.stretch

            bottom       = src.data[data]
            if len(bottom) < 2:
                ind1 = 1
                ind2 = 0
            else:
                delta = bottom[1]-bottom[0]
                ind1  = min(len(bottom), max(0, int((yrng.start-bottom[0])/delta-1)))
                ind2  = min(len(bottom), max(0, int((yrng.end  -bottom[0])/delta+1)))

            if ind1 >= ind2:
                cycles.end = 0
                frames.end = 0
            else:
                frames.end = window.Math.max.apply(None, src.data['frames'][ind1:ind2])+1
                cycles.end = window.Math.max.apply(None, src.data['cycles'][ind1:ind2])+1

        if inpy:
            _onchangebounds(window = type('_Dummy', (), {'Math': np}))
        else:
            fig.y_range.callback = from_py_func(_onchangebounds)

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

class SequencePathWidget(WidgetCreator):
    "Dropdown for choosing a fasta file"
    def __init__(self, model) -> None:
        super().__init__(model)
        self.__widget  = None # type: Optional[Dropdown]
        self.__list    = []   # type: List[str]
        self.__dialog  = None # type: Optional[FileDialog]
        css = self._ctrl.getGlobal("css.plots")
        css.defaults = {'title.fasta'      : u'Open a fasta file',
                        'title.sequence'   : u'Selected DNA sequence',
                        'title.sequence.missing.key' : u'Select sequence',
                        'title.sequence.missing.path': u'Find path'}

    def create(self, action):
        "creates the widget"
        css = self._ctrl.getGlobal("css.plots")
        self.__dialog = FileDialog(filetypes = 'fasta|*',
                                   config    = self._ctrl,
                                   title     = css.title.fasta.get())

        self.__widget = Dropdown(name  = 'Cycles:Sequence',
                                 width = css.inputwidth.get(),
                                 **self.__data())
        @action
        def _py_cb(new):
            if new in self.__list:
                self._model.sequencekey = new
            elif new == '←':
                path = self.__dialog.open()
                seqs = readsequence(path)
                if len(seqs) > 0:
                    self._model.sequencepath = path
                    self._model.sequencekey  = next(iter(seqs))
                else:
                    self.__widget.value = '→'
        self.__widget.on_click(_py_cb)
        return Paragraph(text = css.title.sequence.get()), self.__widget

    def reset(self):
        "updates the widget"
        self.__widget.update(**self.__data())

    def callbacks(self, hover: SequenceHoverMixin, tick1: SequenceTicker):
        "sets-up callbacks for the tooltips and grids"
        ttsource = hover.source
        tick2    = tick1.axis
        @from_py_func
        def _js_cb(cb_obj, tick1 = tick1, tick2 = tick2, src = ttsource):
            if cb_obj.value in src.column_names:
                cb_obj.label     = cb_obj.value
                tick1.key        = cb_obj.value
                tick2.key        = cb_obj.value
                src.data['text'] = src.data[cb_obj.value]
                src.trigger("change")
        self.__widget.js_on_change('value', _js_cb)
        return self.__widget

    @staticmethod
    def _sort(lst) -> List[str]:
        return sorted(lst)

    def __data(self) -> dict:
        lst = self.__list
        lst.clear()
        lst.extend(self._sort(sorted(readsequence(self._model.sequencepath).keys())))

        key   = self._model.sequencekey
        val   = key if key in lst else None
        menu  = [(i, i) for i in lst] if len(lst) else []  # type: List[Optional[Tuple[str,str]]]
        css   = self._ctrl.getGlobal("css.plots").title.sequence
        if len(menu):
            title = css.missing.key.get()
            menu += [None, (title, '←')]
        else:
            title = css.missing.path.get()
            menu += [('', '→'), (title, '←')]
        return dict(menu  = menu,
                    label = title if val is None else key,
                    value = '→'   if val is None else val)

class OligoListWidget(WidgetCreator):
    "Input for defining a list of oligos"
    def __init__(self, model) -> None:
        super().__init__(model)
        self.__widget  = None # type: Optional[AutocompleteInput]
        self.css.defaults = {'title.oligos'     : u'Oligos',
                             'title.oligos.help': u'comma-separated list'}

    def create(self, action):
        "creates the widget"
        self.__widget = AutocompleteInput(**self.__data(),
                                          placeholder = self.css.title.oligos.help.get(),
                                          title       = self.css.title.oligos.get(),
                                          width       = self.css.inputwidth.get(),
                                          name        = 'Cycles:Oligos')

        widget = self.__widget
        match  = re.compile(r'(?:[^atgc]*)([atgc]+)(?:[^atgc]+|$)*',
                            re.IGNORECASE).findall
        @action
        def _py_cb(attr, old, new):
            ols  = sorted(i.lower() for i in match(new))
            hist = self.configroot.oligos.history
            lst  = list(i for i in hist.get() if i != ols)[:hist.maxlength.get()]
            hist.set(([ols] if len(ols) else []) + lst)
            self._model.oligos = ols

        widget.on_change('value', _py_cb)
        return self.__widget

    def reset(self):
        "updates the widget"
        self.__widget.update(**self.__data())

    def __data(self):
        hist = self.configroot.oligos.history.get()
        lst  = [', '.join(sorted(j.lower() for j in i)) for i in hist]
        ols  = ', '.join(sorted(j.lower() for j in self._model.oligos))
        return dict(value = ols, completions = lst)
