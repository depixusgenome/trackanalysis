#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from   typing          import (Optional, List,    # pylint: disable=unused-import
                               Tuple, TYPE_CHECKING)
import re

from    bokeh          import layouts
from    bokeh.models   import (ColumnDataSource,  # pylint: disable=unused-import
                               Slider, CustomJS, Paragraph, Dropdown,
                               AutocompleteInput, DataTable, TableColumn,
                               IntEditor, NumberEditor, ToolbarBox,
                               RadioButtonGroup, CheckboxButtonGroup,
                               CheckboxGroup, Widget)

import  sequences
from  ..dialog                      import FileDialog
from  ..base                        import enableOnTrack
from  ..plotutils                   import (PlotModelAccess, GroupCreator,
                                            readsequence,  WidgetCreator)

from  ._bokehext                    import DpxHoverModel      # pylint: disable=unused-import

class PeaksTableCreator(WidgetCreator):
    "Table of peaks in z and dna units"
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[DataTable]
        self.__hover  = None # type: DpxHoverModel
        self.css.defaults = {'tableheight': 100, 'title.table': u'dna ↔ nm'}

    def create(self, hover):
        "creates the widget"
        height = self.css.tableheight.get()
        width  = self.css.inputwidth.get()
        cols   = [TableColumn(field  = 'bases',
                              title  = self.css.hist.ylabel.get(),
                              editor = IntEditor(),
                              width  = width//2),
                  TableColumn(field  = 'z',
                              title  = self.css.ylabel.get(),
                              editor = NumberEditor(step = 1e-4),
                              width  = width//2)]


        self.__hover  = hover
        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = True,
                                  row_headers = False,
                                  width       = width,
                                  height      = height,
                                  name        = "Cycles:Peaks")
        return Paragraph(text = self.css.title.table.get()), self.__widget

    def update(self):
        "updates the widget"
        self.__widget.source.data = self.__data()

    def callbacks(self, action, stretch, bias):
        "adding callbacks"
        @action
        def _py_cb(attr, old, new):
            zval  = self.__widget.source.data['z']
            bases = self.__widget.source.data['bases']
            peaks = tuple(int(i+.01) for i in bases)
            if peaks != (0, 1000):
                self._model.peaks = peaks
            if zval[0] == zval[1] or bases[0] == bases[1]:
                return

            self._model.stretch = (zval[1]-zval[0]) / (bases[1]-bases[0])
            self._model.bias    = zval[0] - bases[0]*self._model.stretch

        source = self.__widget.source
        source.on_change("data", _py_cb) # pylint: disable=no-member

        obs = lambda: setattr(source, 'data', self.__data())
        self.config.sequence.peaks.observe(obs)
        self.configroot.observe(('oligos', 'last.path.fasta'), obs)
        self.project.sequence.key.observe(obs)

        hover  = self.__hover

        @CustomJS.from_py_func
        def _js_cb(cb_obj = None, mdl = hover, stretch = stretch, bias = bias):
            if mdl.updating != '':
                return
            zval  = cb_obj.data['z']
            bases = cb_obj.data['bases']
            if zval[0] == zval[1] or bases[0] == bases[1]:
                return

            aval = (zval[1]-zval[0]) / (bases[1]-bases[0])
            bval = zval[0] - bases[0]*aval

            stretch.value = aval*1e3
            bias   .value = bval
            mdl.stretch   = aval
            mdl.bias      = bval
            mdl.updating = 'peaks'
            mdl.updating = ''
        source.js_on_change("data", _js_cb) # pylint: disable=no-member

    def __data(self):
        info = self._model.peaks
        if (self._model.sequencekey is not None
                and len(self._model.oligos)
                and info is None):
            seq   = readsequence(self._model.sequencepath)[self._model.sequencekey]
            peaks = sequences.peaks(seq, self._model.oligos)['position']
            if len(peaks) > 2:
                info = peaks[0], peaks[-1]

        if info is None:
            info = 0, 1000

        info += (info[0]*self.__hover.stretch+self.__hover.bias,
                 info[1]*self.__hover.stretch+self.__hover.bias)

        return dict(bases = info[:2], z = info[2:])

class ConversionSlidersCreator(WidgetCreator):
    "Sliders for managing stretch and bias factors"
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.__stretch = None # type: Optional[Slider]
        self.__bias    = None # type: Optional[Slider]
        self.__figdata = None # type: Optional[ColumnDataSource]
        self.css.defaults = {'title.stretch' : u'stretch 10³[dna/nm]',
                             'title.bias'    : u'bias [nm]'}

    def create(self, figdata):
        "creates the widget"
        widget = lambda x, s, e, n: Slider(value = getattr(self._model, x),
                                           title = self.css.title[x].get(),
                                           step  = self.config.base[x].step.get(),
                                           width = self.css.inputwidth.get(),
                                           start = s, end = e, name = n)

        vals = tuple(self.config.base.stretch.get('start', 'end'))
        self.__stretch = widget('stretch', vals[0]*1e3, vals[1]*1e3, 'Cycles:Stretch')
        self.__bias    = widget('bias', -1., 1., 'Cycles:Bias')
        self.__figdata = figdata
        return self.__stretch, self.__bias

    def update(self):
        "updates the widgets"
        minv  = self.__figdata.data['bottom'][0]
        delta = self.__figdata.data['top'][-1] - minv
        ratio = self.config.base.bias.ratio.get()
        self.__bias.update(value = self._model.bias,
                           start = minv,
                           end   = minv+delta*ratio)
        self.__stretch.value = self._model.stretch*1e3

    def callbacks(self, action, hover, table):
        "adding callbacks"
        self.config .base.observe(('stretch', 'bias'), self.update)
        self.project.base.observe(('stretch', 'bias'), self.update)

        stretch, bias = self.__stretch, self.__bias

        # pylint: disable=function-redefined
        def _py_cb(attr, old, new):
            self._model.stretch = new*1e-3
        stretch.on_change('value', action(_py_cb))

        def _py_cb(attr, old, new):
            self._model.bias = new
        bias   .on_change('value', action(_py_cb))

        source = table.source
        @CustomJS.from_py_func
        def _js_cb(stretch = stretch, bias = bias, mdl = hover, source = source):
            if mdl.updating != '':
                return

            mdl.stretch  = stretch.value*1e-3
            mdl.bias     = bias.value
            mdl.updating = 'sliders'

            bases            = source.data['bases']
            source.data['z'] = [bases[0] * stretch.value*1e-3 + bias.value,
                                bases[1] * stretch.value*1e-3 + bias.value]
            source.trigger('change:data')
            mdl.updating = ''

        stretch.js_on_change('value', _js_cb)
        bias   .js_on_change('value', _js_cb)

class SequencePathCreator(WidgetCreator):
    "Dropdown for choosing a fasta file"
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.__widget  = None # type: Optional[Dropdown]
        self.__list    = []   # type: List[str]
        self.__hover   = None # type: Optional[DpxHoverModel]
        self.__dialog  = None # type: Optional[FileDialog]
        self.css.defaults = {'title.fasta'      : u'Open a fasta file',
                             'title.sequence'   : u'Selected DNA sequence',
                             'title.sequence.missing.key' : u'Select sequence',
                             'title.sequence.missing.path': u'Find path'}

    def create(self, action, hover, tick1, tick2):
        "creates the widget"
        self.__dialog = FileDialog(filetypes = 'fasta|*',
                                   config    = self._ctrl,
                                   title     = self.css.title.fasta.get())

        self.__widget = Dropdown(name  = 'Cycles:Sequence',
                                 width = self.css.inputwidth.get(),
                                 **self.__data())
        self.__hover  = hover
        self.__observe(action, tick1, tick2)
        return Paragraph(text = self.css.title.sequence.get()), self.__widget

    def update(self):
        "updates the widget"
        self.__widget.update(**self.__data())

    def __data(self) -> dict:
        lst = self.__list
        lst.clear()
        lst.extend(sorted(readsequence(self._model.sequencepath).keys()))

        key   = self._model.sequencekey
        val   = key if key in lst else None
        menu  = [(i, i) for i in lst] if len(lst) else []  # type: List[Optional[Tuple[str,str]]]
        if len(menu):
            title = self.css.title.sequence.missing.key.get()
            menu += [None, (title, '←')]
        else:
            title = self.css.title.sequence.missing.path.get()
            menu += [('', '→'), (title, '←')]
        return dict(menu  = menu,
                    label = title if val is None else key,
                    value = '→'   if val is None else val)

    def __observe(self, action, tick1, tick2):
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

        widget = self.__widget
        hover  = self.__hover
        src    = hover.source('hist')

        @CustomJS.from_py_func
        def _js_cb(choice  = widget, tick1 = tick1, tick2 = tick2, src = src):
            if choice.value in src.column_names:
                choice.label     = choice.value
                tick1.key        = choice.value
                tick2.key        = choice.value
                src.data['text'] = src.data[choice.value]
                src.trigger("change")
        self.__widget.js_on_change('value', _js_cb)

        obs = lambda: self.__widget.update(**self.__data())
        self.config.sequence.key.observe(obs)
        self.configroot.last.path.fasta.observe(obs)

class OligoListCreator(WidgetCreator):
    "Input for defining a list of oligos"
    def __init__(self, model:PlotModelAccess) -> None:
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
        self.__observe(action)
        return self.__widget

    def update(self):
        "updates the widget"
        self.__widget.update(**self.__data())

    def __data(self):
        hist = self.configroot.oligos.history.get()
        lst  = [', '.join(sorted(j.lower() for j in i)) for i in hist]
        ols  = ', '.join(sorted(j.lower() for j in self._model.oligos))
        return dict(value = ols, completions = lst)

    def __observe(self, action):
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
        self.configroot.oligos.observe(self.update)

class AlignmentCreator(GroupCreator):
    "Allows aligning the cycles on a given phase"
    INPUT = RadioButtonGroup
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.css.title.alignment.labels.default = [u'None', u'Phase 1', u'Phase 3']
        self.css.title.alignment.default        = u'Alignment'

    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        if value == 0:
            self._model.alignment.remove()
        else:
            self._model.alignment.update(phase  = 1 if value == 1 else 3)

    def _data(self):
        task  = self._model.alignment.task
        return dict(active = 0 if task is None else 1 if task.phase == 1 else 2)

class DriftCreator(GroupCreator):
    "Allows removing the drifts"
    INPUT = CheckboxButtonGroup
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.css.title.drift.labels.default = [u'Per bead', u'Per cycle']
        self.css.title.drift.default        = u'Drift Removal'

    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        for ind, name in enumerate(('driftperbead', 'driftpercycle')):
            attr = getattr(self._model, name)
            task = attr.task
            if ind in value and task is None:
                getattr(self._model, name).update()
            elif ind not in value and task is not None:
                getattr(self._model, name).remove()

    def _data(self) -> dict:
        value = [] # type: List[int]
        if self._model.driftperbead.task  is not None:
            value  = [0]
        if self._model.driftpercycle.task is not None:
            value += [1]
        return dict(active = value)

class EventDetectionCreator(GroupCreator):
    "Allows displaying only events"
    INPUT = CheckboxGroup
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.css.title.eventdetection.labels.default = [u'Find events']

    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        task = self._model.eventdetection.task
        if 0 in value and task is None:
            self._model.eventdetection.update()
        elif 0 not in value and task is not None:
            self._model.eventdetection.remove()

    def _data(self) -> dict:
        return dict(active = [] if self._model.eventdetection.task is None else [0])

class ConfigMixin:
    "Everything dealing with config"
    def __init__(self):
        self.__table   = PeaksTableCreator(self._model)
        self.__sliders = ConversionSlidersCreator(self._model)
        self.__seq     = SequencePathCreator(self._model)
        self.__oligs   = OligoListCreator(self._model)
        self.__align   = AlignmentCreator(self._model)
        self.__drift   = DriftCreator(self._model)
        self.__events  = EventDetectionCreator(self._model)
        self.css.inputwidth.default = 205

    def _createconfig(self):
        stretch, bias  = self.__sliders.create(self._histsource)
        table          = self.__table  .create(self._hover)
        oligos         = self.__oligs  .create(self.action)
        parseq,  seq   = self.__seq    .create(self.action, self._hover,
                                               self._gridticker,
                                               self._gridticker.getaxis())
        align  = self.__align  .create(self.action)
        drift  = self.__drift  .create(self.action)
        events = self.__events .create(self.action)

        enableOnTrack(self, self._hist, self._raw,
                      *(i for i in locals().values() if isinstance(i, Widget)))

        self.__sliders.callbacks(self.action, self._hover, table[1])
        self.__table  .callbacks(self.action, stretch, bias)
        return layouts.layout([[layouts.widgetbox([parseq, seq, oligos]),
                                layouts.widgetbox([bias, stretch]),
                                layouts.widgetbox([*table])],
                               [layouts.widgetbox([*i])
                                for i in (align, drift, events)]])

    def _updateconfig(self):
        for ite in self.__dict__.values():
            if isinstance(ite, WidgetCreator):
                ite.update()

    if TYPE_CHECKING:
        # pylint: disable=no-self-use,unused-argument
        config    = None    # type: ignore
        css       = None    # type: ignore
        key       = lambda *_: None
        _figargs  = lambda *_: None
