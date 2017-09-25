#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Create a grid displaying a sequence"
from    typing         import (List, # pylint: disable=unused-import
                               Optional, Tuple, Sequence, TypeVar, cast)
from    collections    import OrderedDict
from    pathlib        import Path
import  numpy   as np

import  bokeh.core.properties as props
from    bokeh.models    import (LinearAxis, ColumnDataSource, Range1d, Widget,
                                BasicTicker, Dropdown, Paragraph, AutocompleteInput)

from    utils           import CachedIO
from    utils.gui       import implementation

from   model.globals        import BeadProperty
from   view.dialog          import FileDialog
from   view.plots.base      import checksizes, WidgetCreator
from   view.plots.bokehext  import DpxHoverTool, from_py_func

from   .                    import (read as _readsequence, peaks as sequencepeaks,
                                    marksequence, splitoligos)
from   .modelaccess         import SequencePlotModelAccess


_CACHE = CachedIO(lambda path: OrderedDict(_readsequence(path)), size = 1)
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

class SequenceTicker(BasicTicker): # pylint: disable=too-many-ancestors
    "Generate ticks at fixed, explicitly supplied locations."
    major      = props.Dict(props.String, props.Seq(props.Float), default = {'': []})
    minor      = props.Dict(props.String, props.Seq(props.Float), default = {'': []})
    key        = props.String(default = '')
    usedefault = props.Bool(default = True)

    __implementation__ = "sequenceticker.coffee"

    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__standoff      = None
        self.__defaults:dict = dict()
        self.__withbase:list = []
        self.__model         = None
        self.__fig           = None
        self.__axis: SequenceTicker = None

    @property
    def axis(self):
        u"returns the fixed axis"
        return self.__axis

    def create(self, fig, mdl, cnf, loc = 'right'):
        "Sets the ticks according to the configuration"
        self.__model = mdl
        self.__fig   = fig
        self.__axis  = type(self)()
        self.__standoff = cnf.css.yrightlabel.standoff

        fig.extra_y_ranges        = {"bases": Range1d(start = 0., end = 1.)}
        fig.add_layout(LinearAxis(y_range_name = "bases",
                                  axis_label   = cnf.css.yrightlabel.get(),
                                  ticker       = self.__axis),
                       loc)

        # bokehjs will never draw minor lines unless the color is
        # is set at startup
        fig.ygrid[0].update(minor_grid_line_color = 'navy',
                            minor_grid_line_alpha = 0.,
                            ticker                = self,
                            y_range_name          = 'bases')

        order  = tuple('grid_line_'+i for i in ('color', 'width', 'dash', 'alpha'))
        order += tuple('minor_'+i for i in order)  # type: ignore
        self.__defaults = {i: getattr(fig.ygrid[0], i) for i in order}

        self.__withbase = dict()
        for name in ('color', 'dash', 'width', 'alpha'):
            gridprops = cnf.css.grid[cnf.css.theme.get()][name].get()
            self.__withbase['grid_line_'+name]       = gridprops[0]
            self.__withbase['minor_grid_line_'+name] = gridprops[1]

    @staticmethod
    def defaultconfig(mdl):
        "default config"
        mdl.css.yrightlabel.standoff.default = -2
        mdl.css.plot.grid.dark.defaults  = dict(color = ('lightgray', 'lightgreen'),
                                                width = (1,          1),
                                                alpha = (.8,         .8),
                                                dash  = ('solid',    'solid'))
        mdl.css.plot.grid.basic.defaults = dict(color = ('lightgray', 'lightgreen'),
                                                width = (1,          1),
                                                alpha = (.8,         .8),
                                                dash  = ('solid',    'solid'))

    def reset(self, resets):
        "Updates the ticks according to the configuration"
        mdl    = self.__model
        fig    = self.__fig
        key    = mdl.sequencekey if mdl.sequencekey is not None and len(mdl.oligos) else 'NONE'
        majors = {}
        minors = {}
        resets[fig.right[-1]].update(axis_label_standoff = self.__standoff.get())
        if key == 'NONE':
            resets[fig.ygrid[0]].update(self.__defaults)
        else:
            resets[fig.ygrid[0]].update(self.__withbase)
            for name, seq in readsequence(mdl.sequencepath).items():
                peaks        = sequencepeaks(seq, mdl.oligos)
                majors[name] = tuple(peaks['position'][peaks['orientation']])
                minors[name] = tuple(peaks['position'][~peaks['orientation']])

        resets[self].update(major = majors, minor = minors, key = key)

        minor = dict.fromkeys(majors.keys(), tuple()) # type:ignore
        major = {i: majors[i]+minors[i] for i in majors}
        resets[self.__axis].update(major = major, minor = minor, key = key)

class SequenceHoverMixin:
    "controls keypress actions"
    def __init__(self):
        self.__source: ColumnDataSource = None
        self.__tool:   DpxHoverTool     = None
        self.__size = None
        self._model = None

    @staticmethod
    def impl(name, fields, extra = None):
        "returns the coffeescript implementation"
        args = ('@define {', '@define {\n        '+fields)
        code = implementation(__file__, args, NAME  = name, extra = extra)
        return code

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

    def reset(self,  resets, **kwa):
        "updates the tooltips for a new file"
        if self.__tool is None:
            return

        data = self.__data()
        resets[self.__source].update(column_names = list(data.keys()), data = data)
        kwa.setdefault('framerate', getattr(self._model.track, 'framerate', 1./30.))
        kwa.setdefault('bias',      self._model.bias)
        kwa.setdefault('stretch',   self._model.stretch)
        resets[self].update(**kwa)

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
            seq        = marksequence(seq, oligs)
            data[name] = np.full((nbases,), ' ', dtype = 'U%d' % osiz)
            data[name][:len(seq)-osiz+1] = [seq[i:i+osiz] for i in range(len(seq)-osiz+1)]

        data['text'] = data.get(key, data[next(iter(dseq))])
        data['z']    = data['values']/mdl.stretch+(0. if mdl.bias is None else mdl.bias)
        return data

ModelType = TypeVar("ModelType", bound = SequencePlotModelAccess)
class SequencePathWidget(WidgetCreator[ModelType]):
    "Dropdown for choosing a fasta file"
    def __init__(self, model) -> None:
        super().__init__(model)
        self.__widget: Dropdown  = None
        self.__list:   List[str] = []
        self.__dialog = FileDialog(filetypes = 'fasta|*',
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
                    if path is not None:
                        raise IOError("Could not find any sequence in the file")

        self.__widget.on_click(_py_cb)
        return [Paragraph(text = self.css.title.sequence.get()), self.__widget]

    def observe(self):
        "sets-up config observers"
        fcn = lambda: self.__widget.update(**self.__data())
        self._model.observeprop('sequencekey', 'sequencepath', fcn)

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget].update(**self.__data())

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
                src.change.emit()
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

class OligoListWidget(WidgetCreator[ModelType]):
    "Input for defining a list of oligos"
    def __init__(self, model) -> None:
        super().__init__(model)
        self.__widget: AutocompleteInput = None
        self.css.plot.defaults = {'oligos.history'          : [],
                                  'oligos.history.maxlength': 10,
                                  'title.oligos'     : u'Oligos',
                                  'title.oligos.help': u'comma-separated list'}

    def create(self, action) -> List[Widget]:
        "creates the widget"
        self.__widget = AutocompleteInput(**self.__data(),
                                          placeholder = self.css.title.oligos.help.get(),
                                          title       = self.css.title.oligos.get(),
                                          width       = self.css.input.width.get(),
                                          name        = 'Cycles:Oligos')

        widget = self.__widget
        @action
        def _py_cb(attr, old, new):
            ols  = splitoligos(new)
            hist = self.css.plot.oligos.history
            lst  = list(i for i in hist.get() if i != ols)[:hist.maxlength.get()]
            hist.set(([ols] if len(ols) else []) + lst)
            self._model.oligos = ols  # type: ignore

        widget.on_change('value', _py_cb)
        return [self.__widget]

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget].update(**self.__data())

    def __data(self):
        hist = self.css.plot.oligos.history.get()
        lst  = [', '.join(sorted(j.lower() for j in i)) for i in hist]
        ols  = ', '.join(sorted(j.lower() for j in self._model.oligos))
        return dict(value = ols, completions = lst)

    def observe(self):
        "sets-up config observers"
        fcn = lambda: self.__widget.update(**self.__data())
        self._model.observeprop('oligos', fcn)

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
            return self # type: ignore

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

    def __get__(self, obj, tpe) -> Optional[str]:  # type: ignore
        val = cast(str, super().__get__(obj, tpe))
        if val is None:
            return getattr(obj, 'estimated'+self._key)
        return cast(str, val)

    def setdefault(self, obj, items:Optional[dict] = None, **kwa):  # type: ignore
        "initializes the property stores"
        super().setdefault(obj,
                           (None if self._key == 'bias' else 1./8.8e-4),
                           items,
                           **kwa)
