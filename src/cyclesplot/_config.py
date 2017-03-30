#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from   typing          import (Optional, List,    # pylint: disable=unused-import
                               Tuple, TYPE_CHECKING)

from    bokeh          import layouts
from    bokeh.models   import (ColumnDataSource,  # pylint: disable=unused-import
                               Slider, CustomJS, Paragraph, Dropdown,
                               AutocompleteInput, DataTable, TableColumn,
                               IntEditor, NumberEditor, ToolbarBox,
                               RadioButtonGroup, CheckboxButtonGroup,
                               CheckboxGroup, Widget)

import  sequences
from    view.plots          import PlotModelAccess, GroupWidget, WidgetCreator as _Widget
from    view.plots.sequence import readsequence, OligoListWidget, SequencePathWidget
from    view.base           import enableOnTrack

from    ._bokehext          import DpxHoverModel      # pylint: disable=unused-import

class PeaksTableWidget(_Widget):
    "Table of peaks in z and dna units"
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[DataTable]
        self.__hover  = None # type: DpxHoverModel
        self.css.defaults = {'tableheight': 100, 'title.table': u'dna ↔ nm'}

    def addinfo(self, hover):
        "adds info to the widget"
        self.__hover = hover

    def create(self, action) -> List[Widget]:
        "creates the widget"
        height = self.css.tableheight.get()
        width  = self.css.inputwidth.get()
        cols   = [TableColumn(field  = 'bases',
                              title  = self.css.yrightlabel.get(),
                              editor = IntEditor(),
                              width  = width//2),
                  TableColumn(field  = 'z',
                              title  = self.css.ylabel.get(),
                              editor = NumberEditor(step = 1e-4),
                              width  = width//2)]

        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = True,
                                  row_headers = False,
                                  width       = width,
                                  height      = height,
                                  name        = "Cycles:Peaks")

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

        self.__widget.source.on_change("data", _py_cb) # pylint: disable=no-member
        return [Paragraph(text = self.css.title.table.get()), self.__widget]

    def reset(self):
        "updates the widget"
        self.__widget.source.data = self.__data()

    def observe(self):
        "sets-up config observers"
        self._model.observeprop('oligos', 'sequencepath', 'sequencekey', self.reset)

    def callbacks(self, stretch, bias):
        "adding callbacks"
        hover = self.__hover
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

        self.__widget.source.js_on_change("data", _js_cb) # pylint: disable=no-member

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

class CyclesSequencePathWidget(SequencePathWidget):
    "SequencePathWidget for cycles"
    def observe(self):
        "sets-up config observers"
        self._model.observeprop('sequencekey', 'sequencepath', self.reset)

class CyclesOligoListWidget(OligoListWidget):
    "OligoListWidget for cycles"
    def observe(self):
        "sets-up config observers"
        self._model.observeprop('oligos', self.reset)

class ConversionSlidersWidget(_Widget):
    "Sliders for managing stretch and bias factors"
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.__stretch = None # type: Optional[Slider]
        self.__bias    = None # type: Optional[Slider]
        self.__figdata = None # type: Optional[ColumnDataSource]
        self.css.defaults = {'title.stretch' : u'stretch 10³[dna/nm]',
                             'title.bias'    : u'bias [nm]'}

    def addinfo(self, histsource):
        "adds info to the widget"
        self.__figdata = histsource

    def create(self, action) -> List[Widget]:
        "creates the widget"
        widget = lambda x, s, e, n: Slider(value = getattr(self._model, x),
                                           title = self.css.title[x].get(),
                                           step  = self.config.base[x].step.get(),
                                           width = self.css.inputwidth.get(),
                                           start = s, end = e, name = n)

        vals = tuple(self.config.base.stretch.get('start', 'end'))
        self.__stretch = widget('stretch', vals[0]*1e3, vals[1]*1e3, 'Cycles:Stretch')
        self.__bias    = widget('bias', -1., 1., 'Cycles:Bias')

        def _py_stretch_cb(attr, old, new):
            self._model.stretch = new*1e-3
        self.__stretch.on_change('value', action(_py_stretch_cb))

        def _py_bias_cb(attr, old, new):
            self._model.bias = new
        self.__bias.on_change('value', action(_py_bias_cb))
        return [self.__stretch, self.__bias]

    def reset(self):
        "updates the widgets"
        minv  = self.__figdata.data['bottom'][0]
        delta = self.__figdata.data['top'][-1] - minv
        ratio = self.config.base.bias.ratio.get()
        self.__bias.update(value = self._model.bias,
                           start = minv,
                           end   = minv+delta*ratio)
        self.__stretch.value = self._model.stretch*1e3

    def observe(self):
        "sets-up config observers"
        self._model.observeprop('stretch', 'bias', self.reset)

    def callbacks(self, hover, table):
        "adding callbacks"
        stretch, bias = self.__stretch, self.__bias
        source        = table.source
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

class AlignmentWidget(GroupWidget):
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

class DriftWidget(GroupWidget):
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

class EventDetectionWidget(GroupWidget):
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
        self.__widget  = dict(table   = PeaksTableWidget(self._model),
                              sliders = ConversionSlidersWidget(self._model),
                              seq     = CyclesSequencePathWidget(self._model),
                              oligs   = CyclesOligoListWidget(self._model),
                              align   = AlignmentWidget(self._model),
                              drift   = DriftWidget(self._model),
                              events  = EventDetectionWidget(self._model))
        self.css.inputwidth.default = 205

    def _createconfig(self):
        self.__widgets['sliders'].addinfo(self._histsource)
        self.__widgets['table']  .addinfo(self._hover)

        widgets = {i: j.create(self.action) for i, j in self.__widgets.items()}
        for widget in self.__widgets.values():
            widget.observe()

        enableOnTrack(self, self._hist, self._raw, *widgets.values())

        self.__widgets['seq']    .callbacks(self._hover.source, self._ticker)
        self.__widgets['sliders'].callbacks(self._hover, widgets['table'][1])
        self.__widgets['table']  .callbacks(*widgets['sliders'])

        return layouts.layout([[layouts.widgetbox(widgets['seq']+widgets['oligos']),
                                layouts.widgetbox(widgets['sliders']),
                                layouts.widgetbox(widgets['table'])],
                               [layouts.widgetbox(widgets[i])
                                for i in ('align', 'drift', 'events')]])

    def _resetconfig(self):
        for ite in self.__dict__.values():
            if isinstance(ite, _Widget):
                ite.reset()

    if TYPE_CHECKING:
        # pylint: disable=no-self-use,unused-argument
        config    = None    # type: ignore
        css       = None    # type: ignore
        key       = lambda *_: None
        _figargs  = lambda *_: None
