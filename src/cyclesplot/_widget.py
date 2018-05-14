#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing              import List, Tuple, Dict, Optional
from    abc                 import ABC

from    bokeh               import layouts
from    bokeh.models        import (ColumnDataSource, Slider, CustomJS, Paragraph,
                                    DataTable, TableColumn, IntEditor, NumberEditor,
                                    CheckboxButtonGroup, Widget)

from    utils               import initdefaults
from    model.task          import RootTask
from    model.task.application import TasksDisplay
from    sequences.view      import OligoListWidget, SequencePathWidget
from    view.plots          import DpxNumberFormatter
from    view.base           import enableOnTrack
from    modaldialog.view    import AdvancedWidgetMixin

from    eventdetection.view import AlignmentWidget, EventDetectionWidget
from    ._model             import CyclesModelAccess, CyclesPlotTheme

class PeaksTableTheme:
    "peaks table theme"
    name    = "peakstable"
    height  = 100
    width   = 60
    title   = 'dna ↔ nm'
    columns = [CyclesPlotTheme.yrightlabel, CyclesPlotTheme.ylabel]
    zstep   = 1e-4
    zformat = '0.0000'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class PeaksTableDisplay:
    "peaks table display"
    name    = "peakstable"
    peaks : Dict[RootTask, Dict[int, Tuple[float, float]]] = {}
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __getitem__(self, tasks: TasksDisplay) -> Optional[Tuple[float, float]]:
        return self.peaks.get(tasks.roottask, {}).get(tasks.bead, None)

class PeaksTableWidget:
    "Table of peaks in z and dna units"
    def __init__(self, tasks:CyclesModelAccess) -> None:
        self.__widget: DataTable = None
        self.__theme             = PeaksTableTheme()
        self.__display           = PeaksTableDisplay()
        self.__tasks             = tasks

    def addtodoc(self, _) -> List[Widget]:
        "creates the widget"
        width  = self.__theme.width
        fmt    = DpxNumberFormatter(format = self.__theme.zformat, text_align = 'right')
        cols   = [TableColumn(field     = 'bases',
                              title     = self.__theme.columns[0],
                              editor    = IntEditor(),
                              width     = width//2),
                  TableColumn(field     = 'z',
                              title     = self.__theme.columns[1],
                              editor    = NumberEditor(step = self.__theme.zstep),
                              formatter = fmt,
                              width     = width//2)]

        self.__widget = DataTable(source         = ColumnDataSource(self.__data()),
                                  columns        = cols,
                                  editable       = True,
                                  index_position = None,
                                  width          = width,
                                  height         = self.__theme.height,
                                  name           = "Cycles:Peaks")

        return [Paragraph(text = self.__theme.title), self.__widget]

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget.source]['data'] = self.__data()

    def observe(self, ctrl):
        "sets-up config observers"
        ctrl.theme.add(self.__theme)
        ctrl.display.add(self.__display)

        fcn = lambda **_: setattr(self.__widget.source, 'data', self.__data())
        ctrl.theme  .observe("sequence", fcn)
        ctrl.display.observe("sequence", fcn)

    def callbacks(self, hover):
        "adding callbacks"
        jsc = CustomJS(code = "hvr.on_change_peaks_table(cb_obj)",
                       args = dict(hvr = hover))
        self.__widget.source.js_on_change("data", jsc) # pylint: disable=no-member

    def __data(self):
        info = self.__display[self.__tasks.sequencemodel.tasks].peaks
        hyb  = self.__tasks.hybridisations(None)
        if hyb is not None  and len(hyb) > 2 and info is None:
            info =  hyb['position'][0], hyb['position'][-1]

        if info is None:
            info = 0, 1000

        stretch, bias = self.__tasks.stretch, self.__tasks.bias
        info         += info[0]/stretch+bias, info[1]/stretch+bias
        return dict(bases = info[:2], z = info[2:])

class ConversionSliderTheme:
    "Conversion slider table theme"
    name    = "conversionslider"
    stretch = dict(start = 900,  step  = 5, end = 1400, title = 'Stretch (base/µm)')
    bias    = dict(step  = 1e-4, ratio = .25, offset = .05, title = 'Bieas (µm)')
    width   = 60
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class ConversionSlidersWidget:
    "Sliders for managing stretch and bias factors"
    def __init__(self, display) -> None:
        self.__display                   = display
        self.__theme                     = ConversionSliderTheme()
        self.__stretch: Slider           = None
        self.__bias:    Slider           = None
        self.__figdata: ColumnDataSource = None

    def addinfo(self, histsource):
        "adds info to the widget"
        self.__figdata = histsource

    def addtodoc(self, _) -> List[Widget]:
        "creates the widget"
        widget = lambda x, s, e, n: Slider(value = getattr(self.__display, x),
                                           title = getattr(self.__theme,  x)['title'],
                                           step  = getattr(self.__theme,  x)['step'],
                                           width = self.__theme.width,
                                           start = s, end = e, name = n)

        vals = tuple(self.__theme.stretch[i] for i in ('start', 'end'))
        self.__stretch = widget('stretch', vals[0], vals[1], 'Cycles:Stretch')
        self.__bias    = widget('bias', -1., 1., 'Cycles:Bias')
        return [self.__stretch, self.__bias]

    def reset(self, resets):
        "updates the widgets"
        ratio  = self.__theme.bias['ratio']
        if resets and self.__figdata in resets and 'data' in resets[self.__figdata]:
            data = resets[self.__figdata]['data']
        else:
            data = self.__figdata.data
        start  = data['bottom'][0]
        end    = start + (data['top'][-1] - start)*ratio
        start -= self.__theme.bias['offset']

        resets[self.__bias].update(value = self.__display.bias, start = start, end = end)
        resets[self.__stretch].update(value = self.__display.stretch)

    def callbacks(self, hover):
        "adding callbacks"
        stretch, bias = self.__stretch, self.__bias

        stretch.js_on_change('value', CustomJS(code = "hvr.on_change_stretch(cb_obj)",
                                               args = dict(hvr = hover)))
        bias   .js_on_change('value', CustomJS(code = "hvr.on_change_bias(cb_obj)",
                                               args = dict(hvr = hover)))

class DriftWidgetTheme:
    "drift widget theme"
    labels = ['Per bead', 'Per cycle']
    title  = 'Drift Removal'

class DriftWidget:
    "Allows removing the drifts"
    def __init__(self, tasks:CyclesModelAccess) -> None:
        self.__theme = DriftWidgetTheme()
        self.__tasks = tasks
        self.__widget: CheckboxButtonGroup = None

    def addtodoc(self, action) -> List[Widget]:
        "creates the widget"
        self.__widget = CheckboxButtonGroup(labels = self.__theme.labels,
                                            name   = 'Cycles:DriftWidget',
                                            **self.__data())
        self.__widget.on_click(action(self._onclick_cb))

        return [Paragraph(text = self.__theme.title), self.__widget]

    def _onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        for ind, name in enumerate(('driftperbead', 'driftpercycle')):
            attr = getattr(self.__tasks, name)
            task = attr.task
            if (ind not in value) != (task is None):
                getattr(self.__tasks, name).update(disabled = ind not in value)

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget].update(**self.__data())

    def observe(self, ctrl):
        "sets-up config observers"
        ctrl.theme.add(self.__theme)

    def __data(self) -> dict:
        value = [] # type: List[int]
        if self.__tasks.driftperbead.task  is not None:
            value  = [0]
        if self.__tasks.driftpercycle.task is not None:
            value += [1]
        return dict(active = value)

class AdvancedWidget(AdvancedWidgetMixin):
    "access to the modal dialog"
    def __init__(self, ctrl, model:CyclesModelAccess) -> None:
        self._model = model
        super().__init__(ctrl)

    @staticmethod
    def _title() -> str:
        return 'Cycles Plot Configuration'

    @staticmethod
    def _body() -> Tuple[Tuple[str,str],...]:
        return (('Histogram bin width',         '%(cycles.theme.binwidth).3f'),
                ('Minimum frames per position', '%(cycles.theme.minframes)d'))

    def _args(self, **kwa):
        return super()._args(model = self._model, **kwa)

    def observe(self, _):
        "sets-up config observers"

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        AdvancedWidgetMixin.reset(resets)

    def addtodoc(self, action) -> List[Widget]:
        "creates the widget"
        return AdvancedWidgetMixin.addtodoc(self, action)

class WidgetMixin(ABC):
    "Everything dealing with changing the config"
    def __init__(self, ctrl):
        self.__widgets = dict(table    = PeaksTableWidget(self._model),
                              sliders  = ConversionSlidersWidget(self._model),
                              seq      = SequencePathWidget(),
                              oligos   = OligoListWidget(),
                              align    = AlignmentWidget(self._model.alignment),
                              drift    = DriftWidget(self._model),
                              events   = EventDetectionWidget(self._model.eventdetection),
                              advanced = AdvancedWidget(ctrl, self._model))

    def ismain(self, ctrl):
        "setup for when this is the main show"
        self.__widgets['advanced'].ismain(ctrl)

    def advanced(self):
        "triggers the advanced dialog"
        self.__widgets['advanced'].on_click()

    def _widgetobservers(self, ctrl):
        for widget in self.__widgets.values():
            widget.observe(ctrl)

    def _createwidget(self):
        self.__widgets['sliders'].addinfo(self._histsource)

        widgets = {i: j.addtodoc(self.action) for i, j in self.__widgets.items()}

        enableOnTrack(self, self._hist, self._raw, widgets)

        self.__widgets['seq']     .callbacks(self._hover, self._ticker)
        self.__widgets['sliders'] .callbacks(self._hover)
        self.__widgets['table']   .callbacks(self._hover)
        self.__widgets['advanced'].callbacks(self._doc)
        self.__slave_to_hover(widgets)

        mds = self.defaultsizingmode()
        return layouts.layout([[layouts.widgetbox(widgets['seq']+widgets['oligos'], **mds),
                                layouts.widgetbox(widgets['sliders'], **mds),
                                layouts.widgetbox(widgets['table'], **mds)],
                               [layouts.widgetbox(widgets[i], **mds)
                                for i in ('align', 'drift', 'events')],
                               [layouts.widgetbox(widgets['advanced'], **mds)]], **mds)

    def _resetwidget(self):
        for ite in self.__widgets.values():
            ite.reset(self._bkmodels)

    def __slave_to_hover(self, widgets):
        jsc = CustomJS(code = "hvr.on_change_hover(table, stretch, bias, fig, ttip)",
                       args = dict(table   = widgets['table'][-1].source,
                                   stretch = widgets['sliders'][0],
                                   bias    = widgets['sliders'][1],
                                   fig     = self._hist,
                                   hvr     = self._hover,
                                   ttip    = self._hover.source))
        self._hover.js_on_change("updating", jsc)
