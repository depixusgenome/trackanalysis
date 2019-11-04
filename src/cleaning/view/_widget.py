#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cleaning beads"
from    typing          import List, Tuple, Union, Optional, Dict

import  bokeh.core.properties as props
from    bokeh.plotting  import Figure
from    bokeh.models    import (ColumnDataSource, DataTable, TableColumn,
                                Widget, StringFormatter, CustomJS, Slider,
                                NumberFormatter)

import  numpy       as     np

from    eventdetection.view      import AlignmentWidget, AlignmentModalDescriptor
from    taskview.modaldialog     import tab
from    taskcontrol.beadscontrol import TaskWidgetEnabler
from    utils                    import initdefaults
from    utils.inspection         import parametercount
from    utils.gui                import parseints, intlistsummary, downloadjs
from    view.static              import route
from    view.plots               import DpxNumberFormatter, CACHE_TYPE
from    ..names                  import NAMES
from    ._model                  import (DataCleaningModelAccess, DataCleaningTask,
                                         CleaningPlotModel, FixedBeadDetectionConfig)

class BeadSubtractionModalDescriptor:
    "for use with modal dialogs"
    def __init__(self, *_):
        self._name = '_subtracted'

    def __set_name__(self, _, name):
        self._name = name

    @staticmethod
    def getdefault(model) -> str:
        "return the modal dialog line"
        mdl = getattr(model, '_model', model)
        pot = intlistsummary([i[-1] for i in mdl.availablefixedbeads], False)
        return f'{pot} ?' if pot else ''

    def line(self) -> Tuple[Union[str, Tuple[str,str]], str]:
        "return the modal dialog line"
        return (('width: 40%', 'Subtracted beads'), f"%({self._name})o220csvi")

    @classmethod
    def text(cls):
        "return the text for creating this line of menu"
        return "%({cls.__name__}:)"

    def __get__(self,inst,owner):
        if inst is None:
            return self
        return getattr(getattr(inst, '_model').subtracted.task, 'beads', [])

    def __set__(self,inst,value):
        getattr(inst, '_model').subtracted.beads = value

class CyclesListTheme:
    "Cycles List Model"
    name    = "cleaning.cycleslist"
    order   = ('population', 'hfsigma', 'extent', 'aberrant',
               'pingpong', 'saturation', 'good')
    width   = 55
    height  = 300
    colors  = CleaningPlotModel.theme.name
    dot     = """
        <div style="border-style:solid;border-color:{};border-radius:5px;float:left;"></div>
        <div>{}</div>
    """.strip()
    columns = [['cycle',      u'Cycle',          '0'],
               ['population', u'% good',         '0.'],
               ['hfsigma',    NAMES['hfsigma'],  '0.0000'],
               ['extent',     NAMES['extent'],   '0.00'],
               ['pingpong',   NAMES['pingpong'], '0.0'],
               ['saturation', u'Non-closing',    ''],
               ['alignment',  'Alignment (µm)',  '0.000'],
               ['clipping',   NAMES['clipping'], '0%'],
               ['discarded',  u'Discarded',      '0%']]
    text     = dict(text_align = 'center', font_style = 'bold')
    number   = dict(text_align = 'right')

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class CyclesListWidget:
    "Table containing stats per peaks"
    __widget: DataTable
    __model:  CyclesListTheme

    def __init__(self, ctrl, task) -> None:
        self.__task   = task
        self.__model  = ctrl.theme.add(CyclesListTheme(), False)
        self.__colors = ctrl.theme.model(self.__model.colors)

    def addtodoc(self, _, ctrl) -> List[Widget]:
        "creates the widget"
        self.__colors = ctrl.theme.model(self.__model.colors)
        if self.__colors is None:
            self.__colors = CleaningPlotModel().theme

        cols          = self.__cols()
        self.__widget = DataTable(source         = ColumnDataSource(self.__data()),
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = self.__model.width*len(cols),
                                  height         = self.__model.height,
                                  name           = "Cleaning:List")
        return [self.__widget]

    def reset(self, resets:CACHE_TYPE):
        "this widget has a source in common with the plots"
        itm  = self.__widget.source if resets is None else resets[self.__widget.source]
        itm.update(data = self.__data())

        itm  = self.__widget if resets is None else resets[self.__widget]
        itm.update(columns = self.__cols())

    def __cols(self):
        dim  = self.__task.instrumentdim
        clrs = self.__colors.colors

        def _dot(i, j):
            return self.__model.dot.format(clrs[i], j) if i in clrs else j

        def _fmt(i, j):
            return (
                StringFormatter(**self.__model.text)
                if i == '' else
                (
                    (NumberFormatter if j else DpxNumberFormatter)
                    (format = i, **self.__model.number)
                )
            )

        return [
            TableColumn(
                field      = i[0],
                title      = _dot(i[0], i[1].replace('µm', dim)),
                formatter  = _fmt(i[2], i[0] == 'alignment')
            ) for i in self.__model.columns
        ]

    def __data(self) -> dict:
        cache = self.__task.cache
        if cache is None or len(cache) == 0:
            return {i: [] for i, _1, _2 in self.__model.columns}
        names = set(i[0] for i in self.__model.columns) & set(cache)
        order = self.__task.sorted(self.__model.order, cache)
        info  = {i: cache[i].values[order] for i in names}

        info['saturation'] = np.zeros(len(order), dtype = 'U1')
        info['saturation'][self.__task.saturatedcycles(cache)] = '✗'
        info['cycle'] = order
        return info

class DownSamplingTheme:
    "stuff for downsampling"
    name:     str = "cleaning.downsampling"
    title:    str = "Plot display dowsampling"
    tooltips: str = (
        "In order to increase the application's response time, "
        "only 1 out of every few data points is displayed"
    )
    policy:   str = "mouseup"
    width:    int = len(CyclesListTheme.columns)*CyclesListTheme.width
    height:   int = 20
    start:    int = 1
    value:    int = 5
    end:      int = 20

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DownsamplingWidget:
    "allows downsampling the graph for greater speed"
    __widget: Slider
    __model:  DownSamplingTheme

    def __init__(self, ctrl):
        self.__model = ctrl.theme.add(DownSamplingTheme(), False)

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = Slider(**{
            i: getattr(self.__model, i.split('_')[-1])
            for i in (
                'title', 'value', 'start', 'end',
                'callback_policy', 'width', 'height'
            )
        })
        @mainview.actionifactive(ctrl)
        def _onchange_cb(attr, old, new):
            ctrl.theme.update(self.__model, value = new)
        self.__widget.on_change("value", _onchange_cb)
        return [self.__widget]

    def reset(self, resets:CACHE_TYPE):
        "this widget has a source in common with the plots"
        itm  = self.__widget if resets is None else resets[self.__widget]
        itm.update(value = self.__model.value)

class DpxCleaning(Widget):
    "Interface to filters needed for cleaning"
    __css__            = route("cleaning.css")
    __javascript__     = route()
    __implementation__ = "_widget.ts"
    frozen             = props.Bool(True)
    framerate          = props.Float(30.)
    figure             = props.Instance(Figure)
    fixedbeads         = props.String("")
    subtracted         = props.String("")
    subtractcurrent    = props.Int(0)

    maxabsvalue        = props.Float(getattr(DataCleaningTask, 'maxabsvalue'))
    maxderivate        = props.Float(getattr(DataCleaningTask, 'maxderivate'))
    minpopulation      = props.Float(getattr(DataCleaningTask, 'minpopulation'))
    minhfsigma         = props.Float(getattr(DataCleaningTask, 'minhfsigma'))
    maxhfsigma         = props.Float(getattr(DataCleaningTask, 'maxhfsigma'))
    minextent          = props.Float(getattr(DataCleaningTask, 'minextent'))
    maxextent          = props.Float(getattr(DataCleaningTask, 'maxextent'))
    maxsaturation      = props.Float(getattr(DataCleaningTask, 'maxsaturation'))

class CleaningFilterTheme:
    "cleaning filter theme"
    width:  int            = len(CyclesListTheme.columns)*CyclesListTheme.width
    height: int            = 230
    name:   str            = "Cleaning:Filter"
    rnd:    Dict[str, int] = dict(
        maxabsvalue   = 1, maxderivate   = 1,
        minpopulation = 1, minhfsigma    = 4,
        minextent     = 2, maxextent     = 2,
        maxhfsigma    = 4, maxsaturation = 0
    )

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class CleaningFilterWidget:
    "All inputs for cleaning"
    __widget: DpxCleaning
    __theme:  CleaningFilterTheme

    def __init__(self, ctrl, model:DataCleaningModelAccess) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(CleaningFilterTheme(), False)

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = DpxCleaning(**{
            i: getattr(self.__theme, i) for i in ('name', 'width', 'height')
        })

        @mainview.actionifactive(ctrl)
        def _on_cb(attr, old, new):
            self.__model.cleaning.update(**{attr: new})
            if attr == 'minpopulation':
                if self.__model.alignment.task is None:
                    self.__model.alignment.configtask = {attr: new}
                else:
                    self.__model.alignment.update(**{attr: new})
                self.__model.clipping.update(**{attr: new})

        for name in ('maxabsvalue', 'maxderivate', 'minpopulation',
                     'minhfsigma',  'maxhfsigma',  'minextent',
                     'maxextent',   'maxsaturation'):
            self.__widget.on_change(name, _on_cb)

        @mainview.actionifactive(ctrl)
        def _on_subtract_cb(attr, old, new):
            self.__model.subtracted.beads = parseints(new)
        self.__widget.on_change('subtracted', _on_subtract_cb)

        @mainview.actionifactive(ctrl)
        def _on_subtract_cur_cb(attr, old, new):
            self.__model.subtracted.switch(self.__model.bead)
        self.__widget.on_change('subtractcurrent', _on_subtract_cur_cb)

        return [self.__widget]

    @property
    def __fixedbeads(self):
        if 'cleaning.theme' in self.__model.ctrl.theme:
            maxi = self.__model.ctrl.theme.get("cleaning.theme", "maxfixedbeads")
        else:
            maxi = CleaningPlotModel().theme.maxfixedbeads

        lst  = [i[-1] for i in self.__model.availablefixedbeads]
        return intlistsummary(lst, False, maxi)

    def observe(self, mainview, ctrl):
        "observe the controller"
        @ctrl.display.observe
        def _onfixedbeads(**_):
            if mainview.isactive():
                self.__widget.fixedbeads = self.__fixedbeads

    def reset(self, resets:CACHE_TYPE):
        "resets the widget when opening a new file, ..."
        mdl  = self.__model
        task = mdl.cleaning.task
        if task is None:
            task = mdl.cleaning.configtask

        info = dict(
            ((i, np.around(getattr(task, i), j)) for i, j in self.__theme.rnd.items()),
            framerate  = getattr(mdl.track, 'framerate', 1./30.),
            subtracted = ', '.join(str(i) for i in sorted(mdl.subtracted.beads)),
            fixedbeads = self.__fixedbeads
        )

        (self.__widget if resets is None else resets[self.__widget]).update(**info)

    def setfigure(self, fig):
        "sets the figure"
        self.__widget.figure = fig
        fig.x_range.callback = CustomJS(
            code = 'mdl.onchangebounds()',
            args = dict(mdl = self.__widget)
        )

class CSVExporter:
    "exports all to csv"
    @staticmethod
    def addtodoc(mainview, _) -> List[Widget]:
        "creates the widget"
        return [downloadjs(
            mainview.getfigure(),
            fname   = "bead.csv",
            tooltip = "Save bead data to CSV",
            src     = mainview.getdata()
        )]

    def reset(self, *_):
        "reset all"

class CleaningWidgets:
    "Everything dealing with changing the config"
    __objects: TaskWidgetEnabler

    def __init__(self, ctrl, model, plotmodel, text = None):
        advanced = tab(
            self.text(text),
            accessors = globals(),
            figure    = plotmodel,
            base      = tab.taskwidget
        )
        self.__widgets = dict(table     = CyclesListWidget(ctrl, model.cleaning),
                              align     = AlignmentWidget(ctrl, model.alignment),
                              cleaning  = CleaningFilterWidget(ctrl, model),
                              sampling  = DownsamplingWidget(ctrl),
                              advanced  = advanced(ctrl, model),
                              csvexport = CSVExporter())

    @staticmethod
    def text(text: Optional[str]) -> str:
        "the default text"
        if text:
            return text
        fix      = FixedBeadDetectionConfig.__name__
        agg      = '%(undersampling.aggregation)|mean:mean|none:none|'
        return f"""
            ## Fixed Beads
            Automatically subtract fixed beads      %({fix}:automate)b
            {NAMES['extent']}  <                    %({fix}:maxextent).3F
            {NAMES['hfsigma']} <                    %({fix}:maxhfsigma).3F
            φ₅ repeatability: max(|z-mean(z)|) <    %({fix}:maxdiff).2F
            drops: dz/dt < -                        %({fix}:drops.mindzdt).3F
            drops: number < cycles ∙                %({fix}:drops.maxdrops)D
            %(BeadSubtractionModalDescriptor:)

            ## Track Undersampling

            ### Reduce the number of frames accross all cycles
            Target frame rate (Hz)                  %(undersampling.framerate)D
            Aggregation                             {agg}

            ### Reduce the number of cycles
            First cycle                             %(undersampling.cyclestart)D
            Last cycle                              %(undersampling.cyclestop)D
            Cycle increment                         %(undersampling.cyclestep)D

            ## Cleaning

            σ[HF]     %(rawprecision.computer)|range:frame-wise|normalized:phase-wise|

            ### Data cleaning
            |z| <                                   %(cleaning.maxabsvalue).1F
            |dz/dt| <                               %(cleaning.maxderivate).3F
            {NAMES['extent']} >                     %(cleaning.minextent).3F
            {NAMES['extent']} <                     %(cleaning.maxextent).3F
            {NAMES['hfsigma']} >                    %(cleaning.minhfsigma).3F
            {NAMES['hfsigma']} <                    %(cleaning.maxhfsigma).3F
            % good frames >                         %(cleaning.minpopulation)D
            {NAMES['pingpong']} <                   %(cleaning.maxpingpong).3F

            ### Non-closing cycles
            Cycles are closed if |z(φ₁)-z(φ₅)| <    %(cleaning.maxdisttozero).3F
            % non-closing cycles <                  %(cleaning.maxsaturation)D

            ### Alignment & post-alignment
            %({AlignmentModalDescriptor.__name__}:)
            % aligned cycles >                      %(alignment.minpopulation)D
            Discard z(∈ φ₅) < z(φ₁)-σ[HF]⋅α, α =    %(clipping.lowfactor).1oF
            % good frames >                         %(clipping.minpopulation)D
        """

    def observe(self, mainview, ctrl):
        "observe the controller"
        for widget in self.__widgets.values():
            pcount: int = parametercount(getattr(widget, 'observe', lambda: None))
            if pcount == 1:
                widget.observe(ctrl)
            elif pcount == 1:
                widget.observe(mainview, ctrl)

        @ctrl.theme.observe("cleaning.downsampling")
        def _ondownsampling(old = None, **_):
            if 'value' in old:
                mainview.reset(False)

    def addtodoc(self, mainview, ctrl, doc, fig):
        "add to the document"
        widgets = {i: j.addtodoc(mainview, ctrl) for i, j in self.__widgets.items()}
        self.__widgets['advanced'].callbacks(doc)
        self.__widgets['cleaning'].setfigure(fig)
        self.__objects = TaskWidgetEnabler(widgets)
        return widgets

    def reset(self, cache: CACHE_TYPE, disable: bool):
        "reset all"
        for ite in self.__widgets.values():
            getattr(ite, 'reset')(cache)
        self.__objects.disable(cache, disable)
