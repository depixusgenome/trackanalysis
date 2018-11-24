#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cleaning beads"
from    typing          import List, Tuple, Union
from    abc             import ABC

import  bokeh.core.properties as props
from    bokeh.plotting  import Figure
from    bokeh.models    import (ColumnDataSource, DataTable, TableColumn,
                                Widget, StringFormatter, CustomJS, Slider)

import  numpy       as     np

from    control.beadscontrol    import TaskWidgetEnabler
from    utils                   import initdefaults
from    utils.gui               import parseints, intlistsummary
from    modaldialog.view        import tab
from    view.static             import route
from    view.plots              import DpxNumberFormatter, CACHE_TYPE
from    eventdetection.view     import (AlignmentWidget, # pylint: disable=unused-import
                                        AlignmentModalDescriptor)
from    ._model                 import (DataCleaningModelAccess, DataCleaningTask,
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
        ref = mdl.subtracted.referencebeads()
        if ref is not None:
            return f'ref = {intlistsummary(ref)}'

        pot = intlistsummary([i[-1] for i in mdl.availablefixedbeads], False)
        return f'{pot} ?' if pot else ''

    def line(self) -> Tuple[Union[str, Tuple[str,str]], str]:
        "return the modal dialog line"
        return (('width: 40%', 'Subtracted beads'), f"%({self._name})220csvi")

    @classmethod
    def text(cls):
        "return the text for creating this line of menu"
        return "%({cls.__name__}:)"

    def __get__(self,inst,owner):
        if inst is None:
            return self
        return getattr(getattr(inst, '_model').subtracted.task, 'beads', [])

    def __set__(self,inst,value):
        subtracted = getattr(inst, '_model').subtracted
        if len(value) == 0:
            subtracted.remove()
        else:
            subtracted.update(beads = list(value))

class CyclesListTheme:
    "Cycles List Model"
    name    = "cleaning.cycleslist"
    order   = ('population', 'hfsigma', 'extent', 'aberrant',
               'pingpong', 'saturation', 'good')
    width   = 65
    height  = 300
    columns = [['cycle',      u'Cycle',       '0'],
               ['population', u'% good',      '0.'],
               ['hfsigma',    u'σ[HF]',       '0.0000'],
               ['extent',     u'Δz',          '0.00'],
               ['pingpong',   u'Σ|dz|',       '0.0'],
               ['saturation', u'Non-closing', ''],
               ['discarded',  u'Discarded',   '']]

class CyclesListWidget:
    "Table containing stats per peaks"
    __widget: DataTable
    __model : CyclesListTheme
    def __init__(self, ctrl, task) -> None:
        self.__task  = task
        self.__model = ctrl.theme.add(CyclesListTheme())

    def addtodoc(self, *_) -> List[Widget]:
        "creates the widget"
        fmt   = lambda i: (StringFormatter(text_align = 'center',
                                           font_style = 'bold') if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = i[1],
                                 formatter  = fmt(i[2]))
                     for i in self.__model.columns)

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
        data = self.__data()
        itm.update(data = data)

    def __data(self) -> dict:
        cache = self.__task.cache
        if cache is None or len(cache) == 0:
            return {i: [] for i, _1, _2 in self.__model.columns}
        names = set(i[0] for i in self.__model.columns) & set(cache)
        bad   = self.__task.nbadcycles(cache)
        order = self.__task.sorted(self.__model.order, cache)
        info  = {i: cache[i].values[order] for i in names}

        info['saturation'] = np.zeros(len(order), dtype = 'U1')
        info['saturation'][self.__task.saturatedcycles(cache)] = '✗'

        info['discarded']  = np.zeros(len(order), dtype = 'U1')
        if len(cache['saturation'].max):
            info['discarded'][:]    = '✗'
        else:
            info['discarded'][:bad] = '✗'

        info['cycle'] = order
        return info

class DownSamplingTheme:
    "stuff for downsampling"
    name     = "cleaning.downsampling"
    title    = "Downsampling"
    tooltips = "Display only 1 out of every few data points"
    policy   = "mouseup"
    start    = 0
    value    = 5
    end      = 5

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DownsamplingWidget:
    "allows downsampling the graph for greater speed"
    __widget: Slider
    __model : DownSamplingTheme
    def __init__(self, ctrl):
        self.__model = ctrl.theme.add(DownSamplingTheme())

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = Slider(**{i: getattr(self.__model, i.split('_')[-1])
                                  for i in ('title', 'value', 'start', 'end',
                                            'callback_policy')})
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
    __implementation__ = "_widget.coffee"
    frozen             = props.Bool(True)
    framerate          = props.Float(30.)
    figure             = props.Instance(Figure)
    fixedbeads         = props.String("")
    subtracted         = props.String("")
    subtractcurrent    = props.Int(0)

    __DFLT             = DataCleaningTask()
    maxabsvalue        = props.Float(__DFLT.maxabsvalue)
    maxderivate        = props.Float(__DFLT.maxderivate)
    minpopulation      = props.Float(__DFLT.minpopulation)
    minhfsigma         = props.Float(__DFLT.minhfsigma)
    maxhfsigma         = props.Float(__DFLT.maxhfsigma)
    minextent          = props.Float(__DFLT.minextent)
    maxextent          = props.Float(__DFLT.maxextent)
    maxsaturation      = props.Float(__DFLT.maxsaturation)
    del __DFLT

class CleaningFilterWidget:
    "All inputs for cleaning"
    RND = dict(maxabsvalue   = 1, maxderivate   = 1,
               minpopulation = 1, minhfsigma    = 4,
               minextent     = 2, maxextent     = 2,
               maxhfsigma    = 4, maxsaturation = 0)
    __widget: DpxCleaning
    def __init__(self, model:DataCleaningModelAccess) -> None:
        self.__model = model

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = DpxCleaning(name = "Cleaning:Filter")

        @mainview.actionifactive(ctrl)
        def _on_cb(attr, old, new):
            self.__model.cleaning.update(**{attr: new})

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
        return intlistsummary([i[-1] for i in self.__model.availablefixedbeads], False)

    def observe(self, ctrl):
        "observe the controller"
        @ctrl.display.observe
        def _onfixedbeads(**_):
            if ctrl.display.model("cleaning").isactive():
                self.__widget.fixedbeads = self.__fixedbeads

    def reset(self, resets:CACHE_TYPE):
        "resets the widget when opening a new file, ..."
        mdl  = self.__model
        task = mdl.cleaning.task
        if task is None:
            task = mdl.cleaning.configtask

        info = dict(
            ((i, np.around(getattr(task, i), j)) for i, j in self.RND.items()),
            framerate  = getattr(mdl.track, 'framerate', 1./30.),
            subtracted = ', '.join(str(i) for i in sorted(mdl.subtracted.beads)),
            fixedbeads = self.__fixedbeads
        )

        (self.__widget if resets is None else resets[self.__widget]).update(**info)

    def setfigure(self, fig):
        "sets the figure"
        self.__widget.figure = fig
        fig.x_range.callback = CustomJS.from_coffeescript('mdl.onchangebounds()',
                                                          dict(mdl = self.__widget))

class WidgetMixin(ABC):
    "Everything dealing with changing the config"
    __objects : TaskWidgetEnabler
    def __init__(self, ctrl, model):
        fix      = FixedBeadDetectionConfig.__name__
        advanced = tab(f"""
           ## Fixed Beads
           Δz <                                 %({fix}:maxextent).3F
           σ[HF] <                              %({fix}:maxhfsigma).3F
           φ5 repeatability: max(|z-mean(z)|) < %({fix}:maxdiff).2F
           %(BeadSubtractionModalDescriptor:)

           ## Cleaning

           |z| <                                 %(cleaning.maxabsvalue).1F
           |dz/dt| <                             %(cleaning.maxderivate).3F
           Δz >                                  %(cleaning.minextent).3F
           Δz <                                  %(cleaning.maxextent).3F
           σ[HF] >                               %(cleaning.minhfsigma).3F
           σ[HF] <                               %(cleaning.maxhfsigma).3F
           % good frames >                       %(cleaning.minpopulation)D
           Cycles are closed if |z(φ1)-z(φ5)| <  %(cleaning.maxdisttozero)D
           % non-closing cycles <                %(cleaning.maxsaturation)D
           <b></b>
           %(AlignmentModalDescriptor:)
           Discard z(∈ φ5) < z(φ1)-σ[HF]⋅α, α =  %(clipping.lowfactor).1oF
           """,
                       accessors = globals(),
                       figure    = CleaningPlotModel,
                       base      = tab.taskwidget)
        self.__widgets = dict(table    = CyclesListWidget(ctrl, model.cleaning),
                              align    = AlignmentWidget(ctrl, model.alignment),
                              cleaning = CleaningFilterWidget(model),
                              sampling = DownsamplingWidget(ctrl),
                              advanced = advanced(ctrl, model))

    def _widgetobservers(self, ctrl):
        for widget in self.__widgets.values():
            if hasattr(widget, 'observe'):
                widget.observe(ctrl)

        def _ondownsampling(old = None, **_):
            if 'value' in old:
                self.reset(False)
        ctrl.theme.observe("cleaning.downsampling", _ondownsampling)

    def _createwidget(self, ctrl, doc, fig):
        widgets = {i: j.addtodoc(self, ctrl) for i, j in self.__widgets.items()}
        self.__widgets['advanced'].callbacks(doc)
        self.__widgets['cleaning'].setfigure(fig)
        self.__objects = TaskWidgetEnabler(widgets)
        return widgets

    def _resetwidget(self, cache: CACHE_TYPE, disable: bool):
        for ite in self.__widgets.values():
            getattr(ite, 'reset')(cache)
        self.__objects.disable(cache, disable)
