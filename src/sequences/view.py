#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Create a grid displaying a sequence"
from    typing              import List, Optional, Tuple, Any
import  numpy               as np
import  bokeh.core.properties as props
from    bokeh.plotting      import Figure
from    bokeh.models        import (LinearAxis, ColumnDataSource, Range1d, Widget,
                                    BasicTicker, Dropdown, CustomJS,
                                    AutocompleteInput)

from   utils                import dataclass, dflt
from   utils.gui            import implementation

from   view.dialog          import FileDialog
from   view.plots.base      import checksizes, themed
from   view.plots.bokehext  import DpxHoverTool

from   .                    import marksequence
from   .modelaccess         import SequenceModel

@dataclass
class SequenceTickerTheme:
    "sequence ticker theme"
    name:     str  = "sequence.ticker"
    standoff: int  = -2
    grid:     dict = dflt({'color': {'dark':  ('lightgray', 'lightgreen'),
                                     'basic': ('gray', 'lightgreen')},
                           'width': (1,          1),
                           'alpha': (.8,         .8),
                           'dash' : ('solid',    'solid')})

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
    __defaults:  dict
    __withbase:  list
    __model:     Any
    __theme:     SequenceTickerTheme
    __fig:       Figure
    __axis:      'SequenceTicker'

    __implementation__ = "sequenceticker.coffee"

    def init(self, ctrl):
        "init private fields"
        self.__defaults:dict = dict()
        self.__withbase:list = []
        self.__theme         = ctrl.theme.add(SequenceTickerTheme(), False)

    @property
    def axis(self):
        u"returns the fixed axis"
        return self.__axis

    def create(self, ctrl, fig, mdl, axlabel, loc = 'right'): # pylint: disable=too-many-arguments
        "Sets the ticks according to the configuration"
        self.__model = mdl
        self.__fig   = fig
        self.__axis  = type(self)()
        self.__axis.init(ctrl)

        fig.extra_y_ranges        = {"bases": Range1d(start = 0., end = 1.)}
        fig.add_layout(LinearAxis(y_range_name = "bases",
                                  axis_label   = axlabel,
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
        theme = self.__model.themename
        for name in ('color', 'dash', 'width', 'alpha'):
            gridprops = themed(theme, self.__theme.grid[name])
            self.__withbase['grid_line_'+name]       = gridprops[0]
            self.__withbase['minor_grid_line_'+name] = gridprops[1]

    def reset(self, resets):
        "Updates the ticks according to the configuration"
        mdl    = self.__model
        fig    = self.__fig
        key    = (mdl.sequencemodel.currentkey
                  if mdl.sequencemodel.currentkey is not None and len(mdl.oligos)
                  else 'NONE')
        majors = {}
        minors = {}
        axis   = next(i for i in fig.right if isinstance(i, LinearAxis))
        resets[axis].update(axis_label_standoff = self.__theme.standoff)
        if key == 'NONE':
            resets[fig.ygrid[0]].update(self.__defaults)
        else:
            resets[fig.ygrid[0]].update(self.__withbase)
            for name, peaks in self.__model.hybridisations(...).items():
                majors[name] = tuple(peaks['position'][peaks['orientation']])
                minors[name] = tuple(peaks['position'][~peaks['orientation']])

        resets[self].update(major = majors, minor = minors, key = key)

        minor = dict.fromkeys(majors.keys(), tuple()) # type:ignore
        major = {i: majors[i]+minors[i] for i in majors}
        resets[self.__axis].update(major = major, minor = minor, key = key)

@dataclass
class SequenceHoverTheme:
    "sequence hover theme"
    name      : str   = "sequence.hover"
    radius    : float = 1.
    policy    : str   = 'follow_mouse'
    tooltips  : str   = '@z{1.1111} ↔ @values: @text'
    oligosize : int   = 4

class SequenceHoverMixin:
    "controls keypress actions"
    __theme:  SequenceHoverTheme
    __source: ColumnDataSource
    __tool:   DpxHoverTool
    _model:   Any
    def init(self, ctrl):
        "initialize"
        self.__theme = ctrl.theme.add(SequenceHoverTheme(), False)

    @staticmethod
    def impl(name, fields, extra = None):
        "returns the coffeescript implementation"
        args = ('@define {', '@define {\n        '+fields)
        code = implementation(__file__, args, NAME  = name, extra = extra)
        return code

    @property
    def source(self):
        "returns the tooltip source"
        return self.__source

    def create(self, fig, mdl, xrng = None):
        "Creates the hover tool for histograms"
        self.update(framerate = 1./30.,
                    bias      = mdl.bias if mdl.bias is not None else 0.,
                    stretch   = mdl.stretch)

        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return
        hover.point_policy = self.__theme.policy
        self._model        = mdl
        self.__tool        = hover[0]
        self.__source      = ColumnDataSource(self.__data())

        args = dict(x                = 'inds',
                    y                = 'values',
                    source           = self.__source,
                    radius           = self.__theme.radius,
                    radius_dimension = 'y',
                    line_alpha       = 0.,
                    fill_alpha       = 0.,
                    y_range_name     = 'bases')
        if xrng is not None:
            args['x_range_name'] = xrng
        self.__tool.update(tooltips  = self.__theme.tooltips,
                           mode      = 'hline',
                           renderers = [fig.circle(**args)])

    def reset(self,  resets, **kwa):
        "updates the tooltips for a new file"
        if self.__tool is None:
            return

        data = self.__data()
        resets[self.__source].update(data = data)
        kwa.setdefault('framerate', getattr(self._model.track, 'framerate', 1./30.))
        kwa.setdefault('bias',      self._model.bias)
        kwa.setdefault('stretch',   self._model.stretch)
        resets[self].update(**kwa)

    @checksizes
    def __data(self):
        mdl   = self._model
        key   = mdl.sequencemodel.currentkey
        oligs = mdl.sequencemodel.currentprobes
        osiz  = max((len(i) for i in oligs), default = self.__theme.oligosize)
        dseq  = mdl.sequences(...)
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

@dataclass
class SequencePathTheme:
    "SequencePathWidgetTheme"
    name       : str = "sequence.path"
    dlgtitle   : str = 'Open a fasta file'
    missingkey : str = 'Select a hairpin sequence'
    missingpath: str = 'Select a hairpin path'
    refcheck   : str = '(ref) '
    inds       : str = '₁₂₃₄₅₆₇₈₉'
    width      : int = 280

class SequencePathWidget:
    "Dropdown for choosing a fasta file"
    _dialog: FileDialog
    _widget: Dropdown
    _theme:  SequencePathTheme
    _model:  SequenceModel
    def __init__(self, ctrl, noerase = False, **kwa):
        self._theme           = ctrl.theme.add(SequencePathTheme(**kwa), noerase = noerase)
        self._model           = SequenceModel().addto(ctrl, noerase = noerase)

    def addtodoc(self, mainview, ctrl, *_) -> List[Widget]:
        "creates the widget"
        self._widget = Dropdown(name  = 'Cycles:Sequence',
                                width = self._theme.width,
                                **self._data())

        mainview.differedobserver(self._data, self._widget,
                                  ctrl.theme,   self._model.config,
                                  ctrl.display, self._model.display)

        @mainview.actionifactive(ctrl)
        def _onclick(new):
            self._onclick(ctrl, new)

        self._widget.on_click(_onclick)
        return [self._widget]

    def observe(self, ctrl):
        "sets-up config observers"
        self._dialog = FileDialog(ctrl,
                                  storage   = "sequence",
                                  title     = self._theme.dlgtitle,
                                  filetypes = 'fasta|txt|*')

    def reset(self, resets):
        "updates the widget"
        resets[self._widget].update(**self._data())

    @property
    def widget(self):
        "returns the widget"
        return self._widget

    def callbacks(self, hover: SequenceHoverMixin, tick1: SequenceTicker):
        "sets-up callbacks for the tooltips and grids"
        if hover is not None:
            jsc = CustomJS(code = ("if(Object.key(src.data).indexOf(cb_obj.value) > -1)"
                                   "{ cb_obj.label     = cb_obj.value;"
                                   "  tick1.key        = cb_obj.value;"
                                   "  tick2.key        = cb_obj.value;"
                                   "  src.data['text'] = src.data[cb_obj.value];"
                                   "  src.change.emit(); }"),
                           args = dict(tick1 = tick1, tick2 = tick1.axis, src = hover.source))
            self._widget.js_on_change('value', jsc)
        return self._widget

    def _data(self) -> dict:
        lst   = sorted(self._model.config.sequences.keys())
        key   = self._model.currentkey
        val   = key if key in lst else None
        label = self._theme.missingkey if val is None else key

        menu: List[Optional[Tuple[str,str]]] = [(i, i) for i in lst]
        menu += [None if len(menu) else ('', '→'), (self._theme.missingpath, '←')]

        return dict(menu  = menu, label = label, value = '→' if val is None else val)

    def _onclick(self, ctrl, new):
        if new == '←':
            path = self._dialog.open()
            self._widget.value = '→'
            if self._model.setnewsequencepath(ctrl, path):
                if path is not None:
                    raise IOError("Could not find any sequence in the file")
        elif new != '→':
            self._model.setnewkey(ctrl, new)

@dataclass
class OligoListTheme:
    "OligoListTheme"
    name   : str = "sequence.probes"
    title  : str = ""
    tooltip: str = 'Oligos: comma-separated list'
    width  : int = 280

class OligoListWidget:
    "Input for defining a list of oligos"
    __widget: AutocompleteInput
    __theme:  OligoListTheme
    __model:  SequenceModel
    def __init__(self, ctrl, noerase = False):
        self.__theme = ctrl.theme.add(OligoListTheme(), noerase = noerase)
        self.__model = SequenceModel().addto(ctrl, noerase = noerase)

    def addtodoc(self, mainview, ctrl, *_) -> List[Widget]:
        "creates the widget"
        css           = [] if self.__theme.title else ["dpx-no-top-margin"]
        self.__widget = AutocompleteInput(**self.__data(),
                                          placeholder = self.__theme.tooltip,
                                          title       = self.__theme.title,
                                          width       = self.__theme.width,
                                          name        = 'Cycles:Oligos',
                                          css_classes = css)

        @mainview.actionifactive(ctrl)
        def _onclick_cb(attr, old, new):
            self.__model.setnewprobes(ctrl, new)
        self.__widget.on_change('value', _onclick_cb)

        mainview.differedobserver(self.__data, self.__widget,
                                  ctrl.theme,   self.__model.config,
                                  ctrl.display, self.__model.display)
        return [self.__widget]

    def reset(self, resets):
        "updates the widget"
        data = self.__data()
        resets[self.__widget].update(**data)

    def __data(self):
        hist = self.__model.config.history
        lst  = [', '.join(sorted(j.lower() for j in i)) for i in hist]
        ols  = ', '.join(sorted(j.lower() for j in self.__model.currentprobes))
        return dict(value = ols, completions = lst)
