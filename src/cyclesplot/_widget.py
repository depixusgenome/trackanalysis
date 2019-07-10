#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing              import List, Tuple, Dict, Optional, Any
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
    name:    str       = "cycles.peakstable"
    height:  int       = 80
    width:   int       = 280
    title:   str       = 'base ↔ µm'
    columns: List[str] = [CyclesPlotTheme.yrightlabel, CyclesPlotTheme.ylabel]
    zstep:   float     = 1e-4
    zformat: str       = '0.0000'
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
    name:    str            = "cycles.conversionslider"
    stretch: Dict[str, Any] = dict(title = 'Stretch (base/µm)', step = 200, ratio = .25)
    bias:    Dict[str, Any] = dict(
        title  = 'Bias (µm)',
        step   = 200,
        ratio  = .25,
        offset = .05
    )
    width:   int            = 280
    height:  int            = 32
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
        args           = dict(step = .1, start = 0, end = 10, value = 5)
        self.__stretch = Slider(
            name   = 'Cycles:Stretch',
            title  = self.__theme.stretch['title'],
            width  = self.__theme.width,
            height = self.__theme.height,
            **args
        )

        self.__bias = Slider(
            name   = 'Cycles:Bias',
            title  = self.__theme.bias['title'],
            width  = self.__theme.width,
            height = self.__theme.height,
            **args
        )
        return [self.__stretch, self.__bias]

    def reset(self, resets:CACHE_TYPE):
        "updates the widgets"
        data = (
            resets[self.__figdata]['data']
            if resets and 'data' in resets.get(self.__figdata, ()) else
            self.__figdata.data
        )
        start  = data['bottom'][0]
        end    = start + (data['top'][-1] - start)*self.__theme.bias['ratio']
        start -= self.__theme.bias['offset']
        resets[self.__bias].update(
            value = self.__display.bias,
            start = start,
            end   = end,
            step  = (end - start)/self.__theme.bias['step']
        )

        center = self.__display.cycles.display.estimatedstretch
        resets[self.__stretch].update(
            value = self.__display.stretch,
            start = center*(1.-self.__theme.stretch['ratio']),
            end   = center*(1.+self.__theme.stretch['ratio']),
            step  = center*2.*self.__theme.stretch['ratio']/self.__theme.bias['step']
        )

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
    name:   str       = 'cycles.drift'
    labels: List[str] = ['Per bead', 'Per cycle']
    width:  int       = 200
    height: int       = 48
    title:  str       = 'dpx-drift-widget'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DriftWidget:
    "Allows removing the drifts"
    __widget: CheckboxButtonGroup
    def __init__(self, ctrl, tasks:CyclesModelAccess) -> None:
        self.__theme = ctrl.theme.add(DriftWidgetTheme())
        self.__tasks = tasks

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = CheckboxButtonGroup(
            labels      = self.__theme.labels,
            name        = 'Cycles:DriftWidget',
            width       = self.__theme.width,
            height      = self.__theme.height,
            css_classes = [self.__theme.title],
            **self.__data()
        )
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

        mode   = self.defaultsizingmode()
        border = ctrl.theme.get("theme", "borders")
        def _items(tpe, itms):
            children = list(itms)
            return getattr(layouts, tpe)(
                children,
                width  = max(i.width  for i in children)+border,
                height = sum(i.height for i in children)+border*len(children)*2,
                **mode,
            )

        def _wbox(names):
            out = _items(
                'widgetbox',
                sum((widgets[i] for i in names.split(',')), [])
            )
            width = max(i.width for i in out.children)
            for i in out.children:
                i.width = width
            return out

        children = [
            _wbox(i)
            for i in ('seq,oligos,align', 'sliders,drift', 'table,events', 'advanced')
        ]
        return layouts.row(
            children,
            width  = sum(i.width for i in children),
            height = max(i.height for i in children),
            **mode
        )

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
