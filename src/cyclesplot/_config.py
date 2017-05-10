#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing          import (Optional, List,    # pylint: disable=unused-import
                                Tuple, TYPE_CHECKING)

from    bokeh          import layouts
from    bokeh.models   import (ColumnDataSource,  # pylint: disable=unused-import
                               Slider, CustomJS, Paragraph, Dropdown,
                               AutocompleteInput, DataTable, TableColumn,
                               IntEditor, NumberEditor, ToolbarBox,
                               RadioButtonGroup, CheckboxButtonGroup,
                               CheckboxGroup, Widget)

import  sequences
from    view.plots          import (PlotModelAccess, GroupWidget,
                                    WidgetCreator as _Widget, DpxNumberFormatter)
from    view.plots.sequence import readsequence, OligoListWidget, SequencePathWidget
from    view.base           import enableOnTrack

from    ._bokehext          import DpxHoverModel      # pylint: disable=unused-import

class PeaksTableWidget(_Widget):
    "Table of peaks in z and dna units"
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[DataTable]
        self.css.table.defaults = {'height' : 100,
                                   'title'  : u'dna ↔ nm',
                                   'zformat': '0.0000'}

    def create(self, action) -> List[Widget]:
        "creates the widget"
        width  = self.css.input.width.get()
        css    = self.css.table
        height = css.height.get()
        fmt    = DpxNumberFormatter(format = css.zformat.get(), text_align = 'right')
        cols   = [TableColumn(field     = 'bases',
                              title     = self.css.yrightlabel.get(),
                              editor    = IntEditor(),
                              width     = width//2),
                  TableColumn(field     = 'z',
                              title     = self.css.ylabel.get(),
                              editor    = NumberEditor(step = 1e-4),
                              formatter = fmt,
                              width     = width//2)]

        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = True,
                                  row_headers = False,
                                  width       = width,
                                  height      = height,
                                  name        = "Cycles:Peaks")

        return [Paragraph(text = css.title.get()), self.__widget]

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget.source]['data'] = self.__data()

    def observe(self):
        "sets-up config observers"
        fcn = lambda: setattr(self.__widget.source, 'data', self.__data())
        self._model.observeprop('oligos', 'sequencepath', 'sequencekey', fcn)

    def callbacks(self, hover):
        "adding callbacks"
        @CustomJS.from_py_func
        def _js_cb(cb_obj = None, mdl = hover):
            if mdl.updating != '':
                return

            zval  = cb_obj.data['z']
            bases = cb_obj.data['bases']
            if zval[0] == zval[1] or bases[0] == bases[1]:
                return

            aval = (bases[1]-bases[0])/(zval[1]-zval[0])
            bval = zval[0] - bases[0]/aval

            if abs(aval - mdl.stretch) < 1e-2 and abs(bval-mdl.bias) < 1e-5:
                return

            mdl.stretch   = aval
            mdl.bias      = bval
            mdl.updating  = 'table'

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

        stretch, bias = self._model.stretch, self._model.bias
        info         += info[0]/stretch+bias, info[1]/stretch+bias
        return dict(bases = info[:2], z = info[2:])

class ConversionSlidersWidget(_Widget):
    "Sliders for managing stretch and bias factors"
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.__stretch = None # type: Optional[Slider]
        self.__bias    = None # type: Optional[Slider]
        self.__figdata = None # type: Optional[ColumnDataSource]

        base = self.css.base
        base.stretch.defaults = dict(start = 900,  step  = 5, end = 1400)
        base.bias   .defaults = dict(step  = 1e-4, ratio = .25)

    def addinfo(self, histsource):
        "adds info to the widget"
        self.__figdata = histsource

    def create(self, action) -> List[Widget]:
        "creates the widget"
        widget = lambda x, s, e, n: Slider(value = getattr(self._model, x),
                                           title = self.css.title[x].get(),
                                           step  = self.css.base[x].step.get(),
                                           width = self.css.input.width.get(),
                                           start = s, end = e, name = n)

        vals = tuple(self.css.base.stretch.get('start', 'end'))
        self.__stretch = widget('stretch', vals[0], vals[1], 'Cycles:Stretch')
        self.__bias    = widget('bias', -1., 1., 'Cycles:Bias')
        return [self.__stretch, self.__bias]

    def reset(self, resets):
        "updates the widgets"
        ratio = self.css.base.bias.ratio.get()
        start = self.__figdata.data['bottom'][0]
        end   = start + (self.__figdata.data['top'][-1] - start)*ratio

        resets[self.__bias].update(value = self._model.bias, start = start, end = end)
        resets[self.__stretch].update(value = self._model.stretch)

    def callbacks(self, hover):
        "adding callbacks"
        stretch, bias = self.__stretch, self.__bias

        @CustomJS.from_py_func
        def _js_stretch_cb(cb_obj = None, mdl = hover):
            if mdl.updating != '':
                return

            if abs(cb_obj.value - mdl.stretch) < 1e-2:
                return

            mdl.stretch   = cb_obj.value
            mdl.updating  = 'stretch'

        stretch.js_on_change('value', _js_stretch_cb)

        @CustomJS.from_py_func
        def _js_bias_cb(cb_obj = None, mdl = hover):
            if mdl.updating != '':
                return

            if abs(cb_obj.value - mdl.bias) < 1e-5:
                return

            mdl.bias      = cb_obj.value
            mdl.updating  = 'bias'
        bias   .js_on_change('value', _js_bias_cb)

class AlignmentWidget(GroupWidget):
    "Allows aligning the cycles on a given phase"
    INPUT = RadioButtonGroup
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self.css.title.alignment.labels.default = [u'None', u'Both', u'Phase 1', u'Phase 3']
        self.css.title.alignment.default        = u'Alignment'

    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        if value == 0:
            self._model.alignment.remove()
        else:
            cnf   = self.config.root.phase
            phase = [None, cnf.initial.get(), cnf.pull.get()][value-1]
            self._model.alignment.update(phase = phase)

    def _data(self):
        task   = self._model.alignment.task
        active = (0 if task       is None else
                  1 if task.phase is None else
                  2 if task.phase == 1    else
                  3)
        return dict(active = active)

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
        self.__widgets = dict(table   = PeaksTableWidget(self._model),
                              sliders = ConversionSlidersWidget(self._model),
                              seq     = SequencePathWidget(self._model),
                              oligos  = OligoListWidget(self._model),
                              align   = AlignmentWidget(self._model),
                              drift   = DriftWidget(self._model),
                              events  = EventDetectionWidget(self._model))

    def _configobservers(self):
        for widget in self.__widgets.values():
            widget.observe()

    def _createconfig(self):
        self.__widgets['sliders'].addinfo(self._histsource)

        widgets = {i: j.create(self.action) for i, j in self.__widgets.items()}

        enableOnTrack(self, self._hist, self._raw, widgets)

        self.__widgets['seq']    .callbacks(self._hover, self._ticker)
        self.__widgets['sliders'].callbacks(self._hover)
        self.__widgets['table']  .callbacks(self._hover)
        self.__slave_to_hover(widgets)

        return layouts.layout([[layouts.widgetbox(widgets['seq']+widgets['oligos']),
                                layouts.widgetbox(widgets['sliders']),
                                layouts.widgetbox(widgets['table'])],
                               [layouts.widgetbox(widgets[i])
                                for i in ('align', 'drift', 'events')]])

    def _resetconfig(self):
        for ite in self.__widgets.values():
            ite.reset(self._bkmodels)

    def __slave_to_hover(self, widgets):
        table         = widgets['table'][-1].source
        stretch, bias = widgets['sliders']
        ttip          = self._hover.source
        fig           = self._hist
        @CustomJS.from_py_func
        def _js_cb(cb_obj  = None, # pylint: disable=too-many-arguments
                   table   = table,
                   stretch = stretch,
                   bias    = bias,
                   fig     = fig,
                   ttip    = ttip):
            if cb_obj.updating == '':
                return

            if cb_obj.updating != 'table':
                bases = table.data["bases"]
                aval  = bases[0] / cb_obj.stretch + cb_obj.bias
                bval  = bases[1] / cb_obj.stretch + cb_obj.bias
                if abs(aval-table.data['z']) < 1e-5 and abs(bval-table.data['z']) < 1e-5:
                    return

                table.data["z"] = [aval, bval]
                table.trigger('change:data') # pylint: disable=no-member

            if cb_obj.updating != 'stretch':
                stretch.value = cb_obj.stretch

            if cb_obj.updating != 'bias':
                bias.value = cb_obj.bias

            cb_obj.apply_update(fig, ttip)

        self._hover.js_on_change("updating", _js_cb)

    if TYPE_CHECKING:
        # pylint: disable=no-self-use,unused-argument
        config    = None    # type: ignore
        css       = None    # type: ignore
        key       = lambda *_: None
        _figargs  = lambda *_: None
