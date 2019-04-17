#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing              import List, Tuple, Dict, Optional
from    abc                 import ABC

from    bokeh               import layouts
from    bokeh.models        import (ColumnDataSource, Slider, CustomJS, DataTable,
                                    TableColumn, IntEditor, NumberEditor,
                                    CheckboxButtonGroup, Widget)

from    eventdetection.view      import AlignmentWidget, EventDetectionWidget
from    taskview.modaldialog     import tab
from    tasksequences.view       import OligoListWidget, SequencePathWidget
from    taskcontrol.beadscontrol import TaskWidgetEnabler
from    taskmodel                import RootTask
from    taskmodel.application    import TasksDisplay
from    utils                    import initdefaults
from    view.plots               import DpxNumberFormatter, CACHE_TYPE
from    ._model                  import (CyclesModelAccess, CyclesPlotTheme,
                                         CyclesModelConfig, CyclesPlotDisplay)

class PeaksTableTheme:
    "peaks table theme"
    name    = "cycles.peakstable"
    height  = 80
    width   = 280
    title   = 'base ↔ µm'
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
        root, bead = tasks.roottask, tasks.bead
        return (None if root is None or bead is None else
                self.peaks.get(root, {}).get(bead, None))

class PeaksTableWidget:
    "Table of peaks in z and dna units"
    __widget: DataTable
    def __init__(self, ctrl, tasks:CyclesModelAccess) -> None:
        self.__theme   = ctrl.theme.add(PeaksTableTheme())
        self.__display = ctrl.display.add(PeaksTableDisplay())
        self.__tasks   = tasks
        self.__ctrl    = ctrl

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = DataTable(source         = ColumnDataSource(self.__data()),
                                  columns        = self.__columns(),
                                  editable       = True,
                                  index_position = None,
                                  width          = self.__theme.width,
                                  height         = self.__theme.height,
                                  name           = "Cycles:Peaks")

        @ctrl.theme.observe
        @ctrl.display.observe
        def _onsequence(**_):
            if mainview.isactive():
                data = self.__data()
                mainview.calllater(lambda: setattr(self.__widget.source, 'data', data))

        return [self.__widget]

    def __columns(self):
        width  = self.__theme.width
        fmt    = DpxNumberFormatter(format = self.__theme.zformat, text_align = 'right')
        track  = self.__ctrl.tasks.track(self.__ctrl.display.get('tasks', "roottask"))
        dim    = track.instrument["dimension"] if track else 'µm'

        def _rep(ind):
            title = self.__theme.columns[ind]
            if 'm)' in title:
                title = title.split('(')[0] + f' ({dim})'
            return title

        return [
            TableColumn(
                field     = 'bases',
                title     = _rep(0),
                editor    = IntEditor(),
                width     = width//2
            ),
            TableColumn(
                field     = 'z',
                title     = _rep(1),
                editor    = NumberEditor(step = self.__theme.zstep),
                formatter = fmt,
                width     = width//2
            )
        ]

    def reset(self, resets:CACHE_TYPE):
        "updates the widget"
        resets[self.__widget.source].update(data = self.__data())
        resets[self.__widget].update(columns = self.__columns())

    def callbacks(self, hover):
        "adding callbacks"
        jsc = CustomJS(code = "hvr.on_change_peaks_table(cb_obj)", args = dict(hvr = hover))
        self.__widget.source.js_on_change("data", jsc) # pylint: disable=no-member

    def __data(self):
        info = self.__display[self.__tasks.sequencemodel.tasks]
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
    name    = "cycles.conversionslider"
    stretch = dict(start = 900,  step  = 5, end = 1400, title = 'Stretch (base/µm)')
    bias    = dict(step  = 1e-4, ratio = .25, offset = .05, title = 'Bias (µm)')
    width   = 280
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class ConversionSlidersWidget:
    "Sliders for managing stretch and bias factors"
    __stretch: Slider
    __bias:    Slider
    __figdata: ColumnDataSource
    def __init__(self, ctrl, display) -> None:
        self.__display = display
        self.__theme   = ctrl.theme.add(ConversionSliderTheme())
        self.__ctrl    = ctrl

    def addinfo(self, histsource):
        "adds info to the widget"
        self.__figdata = histsource

    def addtodoc(self, *_) -> List[Widget]:
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

    def reset(self, resets:CACHE_TYPE):
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

        track  = self.__ctrl.tasks.track(self.__ctrl.display.get('tasks', "roottask"))
        if track:
            dim = track.instrument["dimension"]
            resets[self.__bias].update(title = self.__theme.bias['title'].replace('µm', dim))
            resets[self.__stretch].update(title = self.__theme.stretch['title'].replace('µm', dim))

    def callbacks(self, hover):
        "adding callbacks"
        stretch, bias = self.__stretch, self.__bias

        stretch.js_on_change('value', CustomJS(code = "hvr.on_change_stretch(cb_obj)",
                                               args = dict(hvr = hover)))
        bias   .js_on_change('value', CustomJS(code = "hvr.on_change_bias(cb_obj)",
                                               args = dict(hvr = hover)))

class DriftWidgetTheme:
    "drift widget theme"
    name   = 'cycles.drift'
    labels = ['Per bead', 'Per cycle']
    title  = 'dpx-drift-widget'

class DriftWidget:
    "Allows removing the drifts"
    __widget: CheckboxButtonGroup
    def __init__(self, ctrl, tasks:CyclesModelAccess) -> None:
        self.__theme = ctrl.theme.add(DriftWidgetTheme())
        self.__tasks = tasks

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = CheckboxButtonGroup(labels = self.__theme.labels,
                                            name   = 'Cycles:DriftWidget',
                                            css_classes = [self.__theme.title],
                                            **self.__data())
        self.__widget.on_click(mainview.actionifactive(ctrl)(self._onclick_cb))

        return [self.__widget]

    def _onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        for ind, name in enumerate(('driftperbead', 'driftpercycle')):
            attr = getattr(self.__tasks, name)
            task = attr.task
            if (ind not in value) != (task is None):
                getattr(self.__tasks, name).update(disabled = ind not in value)

    def reset(self, resets:CACHE_TYPE):
        "updates the widget"
        resets[self.__widget].update(**self.__data())

    def __data(self) -> dict:
        value = [] # type: List[int]
        if self.__tasks.driftperbead.task  is not None:
            value  = [0]
        if self.__tasks.driftpercycle.task is not None:
            value += [1]
        return dict(active = value)

class WidgetMixin(ABC):
    "Everything dealing with changing the config"
    __objects: TaskWidgetEnabler
    def __init__(self, ctrl, model):
        cnf = CyclesModelConfig.__name__
        adv = tab(f"""
                  ## Histogram Construction
                  Histogram bin width              %({cnf}:binwidth).3f
                  Minimum frames per hybridisation %({cnf}:minframes)d
                  """,
                  figure    = (CyclesPlotTheme, CyclesPlotDisplay),
                  base      = tab.widget,
                  accessors = globals())

        self.__widgets = dict(table    = PeaksTableWidget(ctrl, model),
                              sliders  = ConversionSlidersWidget(ctrl, model),
                              seq      = SequencePathWidget(ctrl),
                              oligos   = OligoListWidget(ctrl),
                              align    = AlignmentWidget(ctrl, model.alignment),
                              drift    = DriftWidget(ctrl, model),
                              events   = EventDetectionWidget(ctrl, model.eventdetection),
                              advanced = adv(ctrl))

    def ismain(self, ctrl):
        "setup for when this is the main show"
        self.__widgets['advanced'].ismain(ctrl)

    def advanced(self):
        "triggers the advanced dialog"
        self.__widgets['advanced'].on_click()

    def _widgetobservers(self, ctrl):
        for widget in self.__widgets.values():
            if hasattr(widget, 'observe'):
                widget.observe(ctrl)

    def _createwidget(self, ctrl):
        self.__widgets['sliders'].addinfo(self._histsource)

        widgets = {i: j.addtodoc(self, ctrl) for i, j in self.__widgets.items()}
        self.__objects = TaskWidgetEnabler(self._hist, self._raw, widgets)

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

    def _resetwidget(self, cache: CACHE_TYPE, disable: bool):
        for ite in self.__widgets.values():
            ite.reset(cache) # type: ignore
        self.__objects.disable(cache, disable)

    def __slave_to_hover(self, widgets):
        jsc = CustomJS(code = "hvr.on_change_hover(table, stretch, bias, fig, ttip)",
                       args = dict(table   = widgets['table'][-1].source,
                                   stretch = widgets['sliders'][0],
                                   bias    = widgets['sliders'][1],
                                   fig     = self._hist,
                                   hvr     = self._hover,
                                   ttip    = self._hover.source))
        self._hover.js_on_change("updating", jsc)
