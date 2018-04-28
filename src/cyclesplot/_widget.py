#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from    typing              import List, Tuple, TYPE_CHECKING
from    abc                 import ABC

from    bokeh               import layouts
from    bokeh.models        import (ColumnDataSource, Slider, CustomJS, Paragraph,
                                    DataTable, TableColumn, IntEditor, NumberEditor,
                                    CheckboxButtonGroup, Widget)

from    sequences.view      import OligoListWidget, SequencePathWidget
from    view.plots          import GroupWidget, WidgetCreator as _Widget, DpxNumberFormatter
from    view.base           import enableOnTrack
from    modaldialog.view    import AdvancedWidgetMixin

from    eventdetection.view import AlignmentWidget, EventDetectionWidget
from    ._model             import CyclesModelAccess

class PeaksTableWidget(_Widget[CyclesModelAccess]):
    "Table of peaks in z and dna units"
    def __init__(self, model:CyclesModelAccess) -> None:
        super().__init__(model)
        self.__widget: DataTable = None
        self.css.table.defaults  = {'height' : 100,
                                    'title'  : u'dna ↔ nm',
                                    'zformat': '0.0000'}

    def addtodoc(self, _) -> List[Widget]:
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

        self.__widget = DataTable(source         = ColumnDataSource(self.__data()),
                                  columns        = cols,
                                  editable       = True,
                                  index_position = None,
                                  width          = width,
                                  height         = height,
                                  name           = "Cycles:Peaks")

        return [Paragraph(text = css.title.get()), self.__widget]

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget.source]['data'] = self.__data()

    def observe(self, _):
        "sets-up config observers"
        fcn = lambda: setattr(self.__widget.source, 'data', self.__data())
        self._model.observeprop('oligos', 'sequencepath', 'sequencekey', fcn)

    def callbacks(self, hover):
        "adding callbacks"
        jsc = CustomJS(code = "hvr.on_change_peaks_table(cb_obj)",
                       args = dict(hvr = hover))
        self.__widget.source.js_on_change("data", jsc) # pylint: disable=no-member

    def __data(self):
        info = self._model.peaks
        hyb  = self._model.hybridisations(None)
        if hyb is not None  and len(hyb) > 2 and info is None:
            info =  hyb['position'][0], hyb['position'][-1]

        if info is None:
            info = 0, 1000

        stretch, bias = self._model.stretch, self._model.bias
        info         += info[0]/stretch+bias, info[1]/stretch+bias
        return dict(bases = info[:2], z = info[2:])

class ConversionSlidersWidget(_Widget[CyclesModelAccess]):
    "Sliders for managing stretch and bias factors"
    def __init__(self, model:CyclesModelAccess) -> None:
        super().__init__(model)
        self.__stretch: Slider           = None
        self.__bias:    Slider           = None
        self.__figdata: ColumnDataSource = None

        base = self.css.base
        base.stretch.defaults = dict(start = 900,  step  = 5, end = 1400)
        base.bias   .defaults = dict(step  = 1e-4, ratio = .25, offset = .05)

    def addinfo(self, histsource):
        "adds info to the widget"
        self.__figdata = histsource

    def addtodoc(self, _) -> List[Widget]:
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
        ratio  = self.css.base.bias.ratio.get()
        if resets and self.__figdata in resets and 'data' in resets[self.__figdata]:
            data = resets[self.__figdata]['data']
        else:
            data = self.__figdata.data
        start  = data['bottom'][0]
        end    = start + (data['top'][-1] - start)*ratio
        start -= self.css.base.bias.offset.get()

        resets[self.__bias].update(value = self._model.bias, start = start, end = end)
        resets[self.__stretch].update(value = self._model.stretch)

    def callbacks(self, hover):
        "adding callbacks"
        stretch, bias = self.__stretch, self.__bias

        stretch.js_on_change('value', CustomJS(code = "hvr.on_change_stretch(cb_obj)",
                                               args = dict(hvr = hover)))
        bias   .js_on_change('value', CustomJS(code = "hvr.on_change_bias(cb_obj)",
                                               args = dict(hvr = hover)))

class DriftWidget(GroupWidget[CyclesModelAccess]):
    "Allows removing the drifts"
    INPUT = CheckboxButtonGroup
    def __init__(self, model:CyclesModelAccess) -> None:
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

    def observe(self, _):
        "sets-up config observers"

class AdvancedWidget(_Widget[CyclesModelAccess], AdvancedWidgetMixin): # type: ignore
    "access to the modal dialog"
    def __init__(self, ctrl, model:CyclesModelAccess) -> None:
        super().__init__(model)
        AdvancedWidgetMixin.__init__(self, ctrl)

    @staticmethod
    def _title() -> str:
        return 'Cycles Plot Configuration'

    @staticmethod
    def _body() -> Tuple[Tuple[str,str],...]:
        return (('Histogram bin width',         '%(binwidth).3f'),
                ('Minimum frames per position', '%(minframes)d'))

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
                              seq      = SequencePathWidget(self._model),
                              oligos   = OligoListWidget(self._model),
                              align    = AlignmentWidget[CyclesModelAccess](self._model),
                              drift    = DriftWidget(self._model),
                              events   = EventDetectionWidget[CyclesModelAccess](self._model),
                              advanced = AdvancedWidget(ctrl, self._model))

    def ismain(self, ctrl):
        "setup for when this is the main show"
        self.__widgets['advanced'].ismain(ctrl)

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

    def advanced(self):
        "triggers the advanced dialog"
        self.__widgets['advanced'].on_click()

    if TYPE_CHECKING:
        # pylint: disable=no-self-use,unused-argument
        config    = None    # type: ignore
        css       = None    # type: ignore
        key       = lambda *_: None
        _figargs  = lambda *_: None
