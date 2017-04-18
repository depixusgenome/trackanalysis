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
                                CustomJS, Widget)

import  sequences

from    utils           import CachedIO

from   model.globals    import BeadProperty
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

def estimatebias(position: np.ndarray, cnt: np.ndarray) -> float:
    "estimate the bias using the plot data"
    if len(position) < 3:
        return 0.

    ind1 = next((i for i,j in enumerate(cnt) if j > 0), 0)
    ind2 = next((i for i,j in enumerate(cnt[ind1+1:]) if j == 0), ind1+1)
    return position[max(range(ind1,ind2),
                        key     = cnt.__getitem__,
                        default = (ind1+ind2)//2)]

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

            get_ticks_no_defaults: (data_low, data_high, cross_loc, desired_n_ticks) ->
                if @usedefault
                    return @base.get_ticks_no_defaults(data_low, data_high,
                                                       cross_loc, desired_n_ticks)

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
            gridprops = cnf.css.grid[name].get()
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
    def defaultconfig(mdl):
        "default config"
        mdl.css.plot.grid.defaults = dict(color = ('lightblue', 'lightgreen'),
                                          width = (2,           2),
                                          alpha = (1.,          1.),
                                          dash  = ('solid',     'solid'))

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
    def __init__(self):
        self.__source = None # type: Optional[ColumnDataSource]
        self.__tool   = None # type: Optional[DpxHoverTool]
        self.__size   = None # type: Any
        self._model   = None # type: Any

    @staticmethod
    def impl(name, atts):
        "returns the coffeescript implementation"
        return """
                import * as p  from "core/properties"
                import {Model} from "model"
                import {BokehView} from "core/bokeh_view"

                export class %sView extends BokehView
                export class %s extends Model
                    default_view: %sView
                    type:"%s"

                    setsource: (source, values) ->
                        if values[0] == @_values[0] && values[1] == @_values[1]
                            return
                        if values[0] != @bias || values[1] != @stretch
                            return

                        tmp = source.data["values"]
                        source.data["z"] = tmp.map(((x)-> x/@stretch+@bias), @)
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
    def defaultconfig(mdl):
        "default config"
        mdl.css.plot.sequence.defaults = {'tooltips.radius': 1.,
                                          'tooltips.policy': 'follow_mouse',
                                          'tooltips'       : u'@z{1.1111} ↔ @values: @text'}
        mdl.config.plot.oligos.size.default = 4

    @property
    def source(self):
        "returns the tooltip source"
        return self.__source

    def create(self, fig, mdl, cnf, xrng = None):
        "Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = mdl.bias if mdl.bias is not None else 0.,
                    stretch   = mdl.stretch)

        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return
        hover.point_policy = mdl.css.sequence.tooltips.policy.get()
        self._model    = mdl
        self.__tool   = hover[0]
        self.__size   = cnf.config.oligos.size
        self.__source = ColumnDataSource(self.__data())

        css  = cnf.css.sequence.tooltips
        args = dict(x                = 'inds',
                    y                = 'values',
                    source           = self.__source,
                    radius           = css.radius.get(),
                    radius_dimension = 'y',
                    line_alpha       = 0.,
                    fill_alpha       = 0.,
                    y_range_name     = 'bases',
                    visible          = False)
        if xrng is not None:
            args['x_range_name'] = xrng
        self.__tool.update(tooltips  = css.get(),
                           mode      = 'hline',
                           renderers = [fig.circle(**args)])

        src = self.__source
        @from_py_func
        def _js_cb(src = src, fig = fig, cb_obj = None, window = None):
            if cb_obj.updating != '*':
                return

            values = cb_obj.bias, cb_obj.stretch
            window.setTimeout(lambda a, b, c: a.setsource(b, c), 500, cb_obj, src, values)
            bases       = fig.extra_y_ranges['bases']
            yrng        = fig.y_range
            bases.start = (yrng.start-cb_obj.bias)*cb_obj.stretch
            bases.end   = (yrng.end  -cb_obj.bias)*cb_obj.stretch

        self.js_on_change("updating", _js_cb)

    def reset(self, **kwa):
        "updates the tooltips for a new file"
        if self.__tool is None:
            return

        data = self.__data()
        self.__source.update(column_names = list(data.keys()), data = data)
        kwa.setdefault('framerate', getattr(self._model.track, 'framerate', 1./30.))
        kwa.setdefault('bias',      self._model.bias)
        kwa.setdefault('stretch',   self._model.stretch)
        self.update(**kwa)

    def slaveaxes(self, fig, src, normal:str, extra:str, column:str, inpy = False):
        "slaves a histogram's axes to its y-axis"
        # pylint: disable=too-many-arguments,protected-access
        hvr = self
        def _onchangebounds(fig = fig, hvr = hvr, src = src):
            yrng = fig.y_range
            if hasattr(yrng, '_initial_start') and yrng.bounds is not None:
                yrng._initial_start = yrng.bounds[0]
                yrng._initial_end   = yrng.bounds[1]

            if not hasattr(fig, 'extra_x_ranges'):
                return

            cycles = fig.extra_x_ranges[extra]
            frames = fig.x_range

            cycles.start = 0.
            frames.start = 0.

            bases        = fig.extra_y_ranges['bases']
            bases.start  = (yrng.start - hvr.bias)*hvr.stretch
            bases.end    = (yrng.end   - hvr.bias)*hvr.stretch

            bottom       = src.data[column]
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
                frames.end = max(src.data[normal][ind1:ind2])+1
                cycles.end = max(src.data[extra][ind1:ind2])+1

        if inpy:
            _onchangebounds()
        else:
            fig.y_range.callback = from_py_func(_onchangebounds,
                                                normal = normal,
                                                extra  = extra,
                                                column = column)

    @checksizes
    def __data(self):
        mdl   = self._model
        key   = mdl.sequencekey
        oligs = mdl.oligos
        osiz  = max((len(i) for i in oligs), default = self.__size.get())
        dseq  = readsequence(mdl.sequencepath)
        if len(dseq) == 0:
            return dict(values = [0], inds = [0], text = [''], z = [0])

        nbases = max(len(i) for i in dseq.values())
        data   = dict(values = np.arange(osiz, nbases+osiz),
                      inds   = np.full((nbases,), 1, dtype = 'f4'))
        for name, seq in dseq.items():
            seq        = sequences.marksequence(seq, oligs)
            data[name] = np.full((nbases,), ' ', dtype = 'U%d' % osiz)
            data[name][:len(seq)-osiz+1] = [seq[i:i+osiz] for i in range(len(seq)-osiz+1)]

        data['text'] = data.get(key, data[next(iter(dseq))])
        data['z']    = data['values']/mdl.stretch+(0. if mdl.bias is None else mdl.bias)
        return data

class SequencePathWidget(WidgetCreator):
    "Dropdown for choosing a fasta file"
    def __init__(self, model) -> None:
        super().__init__(model)
        self.__widget  = None # type: Optional[Dropdown]
        self.__list    = []   # type: List[str]
        self.__dialog  = FileDialog(filetypes = 'fasta|*',
                                    config    = self._ctrl,
                                    storage   = 'sequence')
        css = self.css.plot.title
        css.defaults = {'fasta'                : u'Open a fasta file',
                        'sequence'             : u'Selected DNA sequence',
                        'sequence.missing.key' : u'Select sequence',
                        'sequence.missing.path': u'Find path'}

    def create(self, action) -> List[Widget]:
        "creates the widget"
        self.__dialog.title = self.css.title.fasta.get()
        self.__widget       = Dropdown(name  = 'Cycles:Sequence',
                                       width = self.css.input.width.get(),
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
        return [Paragraph(text = self.css.title.sequence.get()), self.__widget]

    def observe(self):
        "sets-up config observers"
        self._model.observeprop('sequencekey', 'sequencepath', self.reset)

    def reset(self):
        "updates the widget"
        self.__widget.update(**self.__data())

    @property
    def widget(self):
        "returns the widget"
        return self.__widget

    def callbacks(self, hover: SequenceHoverMixin, tick1: SequenceTicker):
        "sets-up callbacks for the tooltips and grids"
        tick2 = tick1.axis
        src   = hover.source
        @from_py_func
        def _js_cb(tick1 = tick1, tick2 = tick2, src = src, cb_obj = None):
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
        css   = self.css.title.sequence
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
        self.config.plot.oligos.defaults = {'history': [], 'history.maxlength': 10}
        self.css.plot.defaults = {'title.oligos'     : u'Oligos',
                                  'title.oligos.help': u'comma-separated list'}

    def create(self, action) -> List[Widget]:
        "creates the widget"
        self.__widget = AutocompleteInput(**self.__data(),
                                          placeholder = self.css.title.oligos.help.get(),
                                          title       = self.css.title.oligos.get(),
                                          width       = self.css.input.width.get(),
                                          name        = 'Cycles:Oligos')

        widget = self.__widget
        match  = re.compile(r'(?:[^atgc]*)([atgc]+)(?:[^atgc]+|$)*',
                            re.IGNORECASE).findall
        @action
        def _py_cb(attr, old, new):
            ols  = sorted(i.lower() for i in match(new))
            hist = self.config.plot.oligos.history
            lst  = list(i for i in hist.get() if i != ols)[:hist.maxlength.get()]
            hist.set(([ols] if len(ols) else []) + lst)
            self._model.oligos = ols

        widget.on_change('value', _py_cb)
        return [self.__widget]

    def reset(self):
        "updates the widget"
        self.__widget.update(**self.__data())

    def __data(self):
        hist = self.config.oligos.history.get()
        lst  = [', '.join(sorted(j.lower() for j in i)) for i in hist]
        ols  = ', '.join(sorted(j.lower() for j in self._model.oligos))
        return dict(value = ols, completions = lst)

    def observe(self):
        "sets-up config observers"
        self._model.observeprop('oligos', self.reset)

class SequenceKeyProp(BeadProperty[Optional[str]]):
    "access to the sequence key"
    def __init__(self):
        super().__init__('sequence.key')

    def fromglobals(self, obj) -> Optional[str]:
        "returns the current sequence key stored in globals"
        return super().__get__(obj, None)

    def __get__(self, obj, tpe) -> Optional[str]:
        "returns the current sequence key"
        if obj is None:
            return self

        key  = self.fromglobals(obj)
        if key is not None:
            return key

        dseq = readsequence(obj.sequencepath)
        return next(iter(dseq), None) if key not in dseq else key

class FitParamProp(BeadProperty[float]):
    "access to bias or stretch"
    def __init__(self, attr):
        super().__init__('base.'+attr)
        self._key = attr

    def __get__(self, obj, tpe) -> Optional[str]:
        val = super().__get__(obj, tpe)
        if val is None:
            return getattr(obj, 'estimated'+self._key)
        return val

    def setdefault(self, obj, items:Optional[dict] = None, **kwa):
        "initializes the property stores"
        super().setdefault(obj,
                           (None if self._key == 'bias' else 1./8.8e-4),
                           items,
                           **kwa)
