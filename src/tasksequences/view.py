#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Create a grid displaying a sequence"
from    pathlib             import Path
from    typing              import List, Optional, Tuple, Any, Dict, Union
import  numpy               as np
import  bokeh.core.properties as props
from    bokeh.plotting      import Figure
from    bokeh.models        import (LinearAxis, ColumnDataSource, Range1d, Widget,
                                    BasicTicker, Dropdown, CustomJS,
                                    AutocompleteInput)
from    bokeh.util.compiler import TypeScript

from   utils                import dataclass, dflt
from   view.plots           import checksizes, themed
from   view.dialog          import FileDialog
from   .                    import marksequence
from   .modelaccess         import SequencePlotModelAccess, SequenceDisplay

@dataclass
class SequenceTickerTheme:
    "sequence ticker theme"
    name:     str  = "sequence.ticker"
    standoff: int  = -2
    grid:     dict = dflt({'color': {'dark':  ('lightgray', 'lightgreen'),
                                     'basic': ('gray', 'lightgreen')},
                           'width': (1,          1),
                           'alpha': (.8,         .8),
                           'dash':  ('solid',    'solid')})

def estimatebias(position: np.ndarray, cnt: np.ndarray) -> float:
    "estimate the bias using the plot data"
    if len(position) < 3:
        return 0.

    ind1 = next((i for i,j in enumerate(cnt) if j > 0), 0)
    ind2 = next((i for i,j in enumerate(cnt[ind1+1:]) if j == 0), ind1+1)
    return position[max(range(ind1,ind2),
                        key     = cnt.__getitem__,
                        default = (ind1+ind2)//2)]

class SequenceTicker(BasicTicker):  # pylint: disable=too-many-ancestors
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

    __implementation__ = "sequenceticker.ts"

    def __init__(  # pylint: disable=too-many-arguments
            self,
            ctrl    = None,
            fig     = None,
            mdl     = None,
            axlabel = None,
            loc     = 'right',
            **kwa
    ):
        "Sets the ticks according to the configuration"
        super().__init__(**kwa)
        self.__defaults = dict()
        self.__withbase = []
        if ctrl:
            self.__theme = ctrl.theme.add(SequenceTickerTheme(), False)
        else:
            self.__theme = SequenceTickerTheme()
        if mdl is None:
            return

        self.__model = mdl
        self.__fig   = fig
        self.__axis  = type(self)(ctrl)

        if 'bases' not in fig.extra_y_ranges:
            fig.extra_y_ranges = dict(fig.extra_y_ranges, bases = Range1d(start = 0., end = 0.))
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

    @staticmethod
    def init(ctrl):
        "init private fields"
        ctrl.theme.add(SequenceTickerTheme(), False)

    @property
    def axis(self):
        u"returns the fixed axis"
        return self.__axis

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

        minor = dict.fromkeys(majors.keys(), tuple())  # type:ignore
        major = {i: majors[i]+minors[i] for i in majors}
        resets[self.__axis].update(major = major, minor = minor, key = key)

@dataclass
class SequenceHoverTheme:
    "sequence hover theme"
    name:      str   = "sequence.hover"
    radius:    float = 1.
    policy:    str   = 'follow_mouse'
    tooltips:  str   = '@z{1.1111} ↔ @values: @text'
    oligosize: int   = 4

class SequenceHoverMixin:
    "controls keypress actions"
    @staticmethod
    def init(ctrl):
        "initialize"
        ctrl.theme.add(SequenceHoverTheme(), False)

    @classmethod
    def impl(
            cls,
            name:   str,
            fields: Dict[str, Tuple[str,...]],
            extra:  Union[None, str, Path] = None
    ) -> TypeScript:
        "returns the typescript implementation"
        path = Path(__file__).with_suffix('.ts')
        if not path.exists():
            return ""

        code     = ''.join(open(path))
        line     = '\n'+'    '*3
        internal = {i: j for i, j in fields.items() if i[0] == '_'}
        cumpy    = {i: j for i, j in fields.items() if i[0] != '_'}
        for title, fcn, itms in [
                ('.Props & {',    lambda i, j: f'{i}: p.Property<{j[1]}>', fields),
                ('this.define<NAME.Props>({', lambda i, j: f'{i}: {j[0]},', cumpy)
        ]:
            repl = line+line.join(fcn(i, j) for i, j in itms.items())
            code = code.replace(title, title+repl)

        if internal:
            repl = '{'+line+line.join(fcn(i, j) for i, j in internal.items())[:-1]+'}'
            code = code.replace('this.define', f'this.internal({repl})\n        this.define')

        code = code.replace('NAME', name)
        if extra:
            code = cls.__impl_extra(code, extra)
        return TypeScript(code)

    @property
    def source(self):
        "returns the tooltip source"
        return self.renderers[0].data_source

    @classmethod
    def create(cls, ctrl, doc, fig, mdl, xrng = None):  # pylint: disable=too-many-arguments
        "Creates the hover tool for histograms"
        theme = ctrl.theme.add(SequenceHoverTheme(), False)
        args  = dict(x                = 'inds',
                     y                = 'values',
                     source           = ColumnDataSource(cls.__data(ctrl, mdl)),
                     radius           = theme.radius,
                     radius_dimension = 'y',
                     line_alpha       = 0.,
                     fill_alpha       = 0.,
                     x_range_name     = xrng,
                     y_range_name     = 'bases')
        if xrng is None:
            args.pop('x_range_name')

        self = cls(framerate    = 30.,
                   bias         = mdl.bias if mdl.bias is not None else 0.,
                   stretch      = mdl.stretch,
                   point_policy = theme.policy,
                   tooltips     = theme.tooltips,
                   mode         = 'hline',
                   renderers    = [fig.circle(**args)])
        fig.add_tools(self)

        done = [False]

        @ctrl.display.observe(SequenceDisplay().name)
        def _onchange(old = None, **_):
            if (
                    done[0]
                    or 'hpins' not in old
                    or fig in doc.select({'type': Figure}) and not done[0]
            ):
                return

            done[0] = True
            @doc.add_next_tick_callback
            def _fcn():
                done[0] = False
                # pylint: disable=protected-access
                self.source.update(data = self.__data(ctrl, mdl))
        return self

    def reset(self, resets, ctrl, model, **kwa):
        "updates the tooltips for a new file"
        data = self.__data(ctrl, model)
        resets[self.source].update(data = data)
        kwa.setdefault('framerate', getattr(model.track, 'framerate', 30.))
        kwa.setdefault('bias',      model.bias)
        kwa.setdefault('stretch',   model.stretch)
        resets[self].update(**kwa)

    @staticmethod
    @checksizes
    def __data(ctrl, mdl):
        size  = ctrl.theme.get(SequenceHoverTheme(), "oligosize")
        key   = mdl.sequencemodel.currentkey
        oligs = mdl.sequencemodel.currentprobes
        osiz  = max((len(i) for i in oligs), default = size)
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

    @staticmethod
    def __impl_extra(code:str, extra:Union[str, Path]) -> str:
        lines = open(Path(extra).with_suffix('.ts'), encoding = 'utf-8').readlines()
        ind   = max((i for i, j in enumerate(lines) if j.startswith('import ')), default = 0)
        imps  = lines[:ind+1]
        ind   = code.rfind('}')
        return (
            ''.join(imps)
            + code[:ind]
            + '\n'
            + ''.join(lines[len(imps):])
            + code[ind:]
        )

@dataclass      # pylint: disable=too-many-instance-attributes
class SequencePathTheme:
    "SequencePathWidgetTheme"
    name:        str = "sequence.path"
    dlgtitle:    str = 'Open a fasta file'
    missingkey:  str = 'Select a hairpin sequence'
    missingpath: str = 'Select a hairpin path'
    refcheck:    str = '(ref) '
    inds:        str = '₁₂₃₄₅₆₇₈₉'
    width:       int = 280
    height:      int = 32

class SequencePathWidget:
    "Dropdown for choosing a fasta file"
    _dialog: FileDialog
    _widget: Dropdown
    _theme:  SequencePathTheme
    _model:  SequencePlotModelAccess

    def __init__(self, ctrl, **kwa):
        self._theme = ctrl.theme.swapmodels(SequencePathTheme(**kwa))
        self._model = SequencePlotModelAccess()
        self._model.swapmodels(ctrl)

    def addtodoc(self, mainview, ctrl, *_) -> List[Widget]:
        "creates the widget"
        self._widget = Dropdown(name   = 'Cycles:Sequence',
                                width  = self._theme.width,
                                height = self._theme.height,
                                **self._data())

        mainview.differedobserver(self._data, self._widget,
                                  ctrl.theme,   self._model.sequencemodel.config,
                                  ctrl.display, self._model.sequencemodel.display)

        self._widget.on_click(ctrl.action(self._onclick))
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
            jsc = CustomJS(code = ("if(Object.keys(src.data).indexOf(cb_obj.value) > -1)"
                                   "{ cb_obj.label     = cb_obj.value;"
                                   "  tick1.key        = cb_obj.value;"
                                   "  tick2.key        = cb_obj.value;"
                                   "  src.data['text'] = src.data[cb_obj.value];"
                                   "  src.change.emit(); }"),
                           args = dict(tick1 = tick1, tick2 = tick1.axis, src = hover.source))
            self._widget.js_on_change('value', jsc)
        return self._widget

    def _data(self) -> dict:
        lst   = sorted(self._model.sequencemodel.config.sequences.keys())
        key   = self._model.sequencemodel.currentkey
        val   = key if key in lst else None
        label = self._theme.missingkey if val is None else key

        menu: List[Optional[Tuple[str,str]]] = [(i, i) for i in lst]
        menu += [None if len(menu) else ('', '→'), (self._theme.missingpath, '←')]

        return dict(menu  = menu, label = label, value = '→' if val is None else val)

    def _onclick(self, new):
        if new.item == '←':
            path = self._dialog.open()
            self._widget.value = '→'
            if self._model.setnewsequencepath(path):
                if path is not None:
                    raise IOError("Could not find any sequence in the file")
        elif new.item != '→':
            self._model.setnewsequencekey(new.item)

@dataclass
class OligoListTheme:
    "OligoListTheme"
    name:    str = "sequence.probes"
    title:   str = ""
    tooltip: str = 'c!cwgg, aat, +aaa, 0, singlestrand ...?'
    width:   int = 280
    height:  int = 32

class DpxAutocompleteInput(AutocompleteInput):  # pylint: disable=too-many-ancestors
    "autocomplete which allows having no selection"
    __implementation__ = "_autocomplete.ts"

class OligoListWidget:
    "Input for defining a list of oligos"
    __widget: DpxAutocompleteInput
    __theme:  OligoListTheme
    __model:  SequencePlotModelAccess

    def __init__(self, ctrl):
        self.__theme = ctrl.theme.swapmodels(OligoListTheme())
        self.__model = SequencePlotModelAccess()
        self.__model.swapmodels(ctrl)

    def addtodoc(self, mainview, ctrl, *_) -> List[Widget]:
        "creates the widget"
        self.__widget = DpxAutocompleteInput(
            **self.__data(),
            placeholder = self.__theme.tooltip,
            title       = self.__theme.title,
            width       = self.__theme.width,
            height      = self.__theme.height,
            name        = 'Cycles:Oligos'
        )

        fcn = ctrl.action(lambda attr, old, new: self.__model.setnewprobes(new))
        self.__widget.on_change('value', fcn)

        mainview.differedobserver(self.__data, self.__widget,
                                  ctrl.theme,   self.__model.sequencemodel.config,
                                  ctrl.display, self.__model.sequencemodel.display)
        return [self.__widget]

    def reset(self, resets):
        "updates the widget"
        data = self.__data()
        resets[self.__widget].update(**data)

    def __data(self):
        hist = self.__model.sequencemodel.config.history
        lst  = [', '.join(sorted(j.lower() for j in i)) for i in hist]
        ols  = ', '.join(sorted(j.lower() for j in self.__model.sequencemodel.currentprobes))
        return dict(value = ols, completions = lst)
