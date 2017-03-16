#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widgets for configuration"

from   typing          import (Optional, List,    # pylint: disable=unused-import
                               Tuple, TYPE_CHECKING)
import re

from    bokeh          import layouts
from    bokeh.models   import (ColumnDataSource,  # pylint: disable=unused-import
                               Slider, CustomJS, Paragraph, Dropdown,
                               TextInput, DataTable, TableColumn,
                               IntEditor, NumberEditor, ToolbarBox)

import  sequences
from    control         import Controller
from  ..dialog          import FileDialog
from  ..base            import enableOnTrack
from  ..plotutils       import TrackPlotModelController, readsequence,  WidgetCreator

from  ._bokehext        import DpxHoverModel      # pylint: disable=unused-import

class _PeakTableCreator(WidgetCreator):
    "Table creator"
    def __init__(self, ctrl:Controller, model:TrackPlotModelController, key:str) -> None:
        super().__init__(ctrl, model, key)
        self.__widget = None # type: Optional[DataTable]
        self.__hover  = None # type: DpxHoverModel
        self.getCSS().defaults = {'tablesize'   : (200, 100),
                                  'title.table' : u'dna ↔ nm'}

    def create(self, hover):
        "creates the widget"
        size = self.getCSS().tablesize.get()
        cols = [TableColumn(field  = 'bases',
                            title  = self.getCSS().hist.ylabel.get(),
                            editor = IntEditor(),
                            width  = size[0]//2),
                TableColumn(field  = 'z',
                            title  = self.getCSS().ylabel.get(),
                            editor = NumberEditor(step = 1e-4),
                            width  = size[0]//2)]


        self.__hover  = hover
        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = True,
                                  row_headers = False,
                                  width       = size[0],
                                  height      = size[1])
        return Paragraph(text = self.getCSS().title.table.get()), self.__widget

    def update(self):
        "updates the widget"
        self.__widget.source.data = self.__data()

    def __data(self):
        info = self._model.witnesses
        if (self._model.sequencekey is not None
                and len(self._model.oligos)
                and info is None):
            seq   = readsequence(self._model.sequencepath)[self._model.sequencekey]
            peaks = sequences.peaks(seq, self._model.oligos)['position']
            if len(peaks) > 2:
                info = peaks[0], peaks[-1]

        if info is None:
            info = 0., 1e3

        info += (info[0]*self.__hover.stretch+self.__hover.bias,
                 info[1]*self.__hover.stretch+self.__hover.bias)

        return dict(bases = info[:2], z = info[2:])

    def callbacks(self, action, stretch, bias):
        "adding callbacks"
        @action
        def _py_cb(attr, old, new):
            zval  = self.__widget.source.data['z']
            bases = self.__widget.source.data['bases']
            self._model.witnesses = tuple(bases)
            if zval[0] == zval[1] or bases[0] == bases[1]:
                return

            self._model.stretch = (zval[1]-zval[0]) / (bases[1]-bases[0])
            self._model.bias    = zval[0] - bases[0]*self._model.stretch

        source = self.__widget.source
        source.on_change("data", _py_cb) # pylint: disable=no-member

        self.getCurrent().observe(('oligos', 'sequence.witnesses'),
                                  lambda: setattr(source, 'data', self.__data()))

        hover  = self.__hover

        @CustomJS.from_py_func
        def _js_cb(source = source, mdl = hover, stretch = stretch, bias = bias):
            zval  = source.data['z']
            bases = source.data['bases']
            if zval[0] == zval[1] or bases[0] == bases[1]:
                return

            aval = (zval[1]-zval[0]) / (bases[1]-bases[0])
            bval = zval[0] - bases[0]*aval

            stretch.value = aval
            bias   .value = bval
            mdl.stretch   = aval
            mdl.bias      = bval
            mdl.updating += 1
        source.js_on_change("data", _js_cb) # pylint: disable=no-member

class _SliderCreator(WidgetCreator):
    "Slider creator"
    def __init__(self, ctrl:Controller, model:TrackPlotModelController, key:str) -> None:
        super().__init__(ctrl, model, key)
        self.__stretch = None # type: Optional[Slider]
        self.__bias    = None # type: Optional[Slider]
        self.__figdata = None # type: Optional[ColumnDataSource]
        self.getCSS().defaults = {'title.stretch'    : u'stretch [dna/nm]',
                                  'title.bias'       : u'bias [nm]'}

    def create(self, figdata):
        "creates the widget"
        widget = lambda x, s, e: Slider(value = getattr(self._model, x),
                                        title = self.getCSS().title[x].get(),
                                        step  = self.getConfig().base[x].step.get(),
                                        start = s, end = e)

        self.__stretch = widget('stretch', *self.getConfig().base.stretch.get('start', 'end'))
        self.__bias    = widget('bias', -1., 1.)
        self.__figdata = figdata
        return self.__stretch, self.__bias

    def update(self):
        "updates the widgets"
        minv  = self.__figdata.data['bottom'][0]
        delta = self.__figdata.data['top'][-1] - minv
        ratio = self.getConfig().base.bias.ratio.get()
        self.__bias.update(value = self._model.bias,
                           start = minv,
                           end   = minv+delta*ratio)
        self.__stretch.value = self._model.stretch

    def callbacks(self, action, hover, table):
        "adding callbacks"
        self.getConfig() .observe(('base.stretch', 'base.bias'), self.update)
        self.getCurrent().observe(('base.stretch', 'base.bias'), self.update)

        stretch, bias = self.__stretch, self.__bias

        # pylint: disable=function-redefined
        def _py_cb(attr, old, new):
            self._model.stretch = new
        stretch.on_change('value', action(_py_cb))

        def _py_cb(attr, old, new):
            self._model.bias = new
        bias   .on_change('value', action(_py_cb))

        source = table.source
        @CustomJS.from_py_func
        def _js_cb(stretch = stretch, bias = bias, mdl = hover, source = source):
            mdl.stretch  = stretch.value
            mdl.bias     = bias.value
            mdl.updating = mdl.updating+1

            bases            = source.data['bases']
            source.data['z'] = [bases[0] * stretch.value + bias.value,
                                bases[1] * stretch.value + bias.value]
            source.trigger('change:data')

        stretch.js_on_change('value', _js_cb)
        bias   .js_on_change('value', _js_cb)

class _SequenceCreator(WidgetCreator):
    "Sequence Droppdown creator"
    def __init__(self, ctrl:Controller, model:TrackPlotModelController, key:str) -> None:
        super().__init__(ctrl, model, key)
        self.__widget  = None # type: Optional[Dropdown]
        self.__list    = []   # type: List[str]
        self.__hover   = None # type: Optional[DpxHoverModel]
        self.__dialog  = None # type: Optional[FileDialog]
        self.getCSS().defaults = {'title.fasta'      : u'Open a fasta file',
                                  'title.sequence'   : u'Selected DNA sequence',
                                  'title.sequence.missing.key' : u'Select sequence',
                                  'title.sequence.missing.path': u'Find path'}

    def create(self, action, hover, tick1, tick2):
        "creates the widget"
        self.__dialog = FileDialog(filetypes = 'fasta|*',
                                   config    = self._ctrl,
                                   title     = self.getCSS().title.fasta.get())

        self.__widget = Dropdown(**self.__data())
        self.__hover  = hover
        self.__observe(action, tick1, tick2)
        return Paragraph(text = self.getCSS().title.sequence.get()), self.__widget

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
            title = self.getCSS().title.sequence.missing.key.get()
            menu += [None, (title, '←')]
        else:
            title = self.getCSS().title.sequence.missing.path.get()
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

        self.getConfig().observe(('sequence.key', 'sequence.path'),
                                 lambda: self.__widget.update(**self.__data()))

class _OligosCreator(WidgetCreator):
    "Oligo list creator"
    def __init__(self, ctrl:Controller, model:TrackPlotModelController, key:str) -> None:
        super().__init__(ctrl, model, key)
        self.__widget  = None # type: Optional[TextInput]
        self.getCSS().defaults = {'title.oligos'     : u'Oligos',
                                  'title.oligos.help': u'comma-separated list'}

    def create(self, action):
        "creates the widget"
        self.__widget = TextInput(value       = self.__data(),
                                  placeholder = self.getCSS().title.oligos.help.get(),
                                  title       = self.getCSS().title.oligos.get())
        self.__observe(action)
        return self.__widget

    def update(self):
        "updates the widget"
        self.__widget.value = self.__data()

    def __data(self):
        return ', '.join(sorted(j.lower() for j in self._model.oligos))

    def __observe(self, action):
        widget = self.__widget
        match  = re.compile(r'(?:[^atgc]*)([atgc]+)(?:[^atgc]+|$)*',
                            re.IGNORECASE).findall
        @action
        def _py_cb(attr, old, new):
            self._model.oligos = sorted({i.lower() for i in match(new)})
        widget.on_change('value', _py_cb)

        self.getConfig().observe('oligos', lambda: setattr(self.__widget, 'value',
                                                           self.__data()))

class ConfigMixin:
    "Everything dealing with config"
    def __init__(self):
        args           = self._ctrl, self._model, self.key('')
        self.__table   = _PeakTableCreator(*args)
        self.__sliders = _SliderCreator(*args)
        self.__seq     = _SequenceCreator(*args)
        self.__oligs   = _OligosCreator(*args)

    def _createconfig(self):
        stretch, bias  = self.__sliders.create(self._histsource)
        par,     table = self.__table  .create(self._hover)
        oligos         = self.__oligs  .create(self.action)
        parseq,  seq   = self.__seq    .create(self.action, self._hover,
                                               self._gridticker,
                                               self._gridticker.getaxis())

        self.__sliders.callbacks(self.action, self._hover, table)
        self.__table  .callbacks(self.action, stretch, bias)
        ret = layouts.layout([[layouts.widgetbox([parseq, seq]), oligos],
                              [layouts.widgetbox([bias, stretch]),
                               layouts.widgetbox([par,  table])]])

        enableOnTrack(self, self._hist, self._raw, stretch, bias, oligos, seq, table)
        return ret

    def _updateconfig(self):
        self.__sliders.update()
        self.__table.update()
        self.__oligs.update()
        self.__seq.update()

    if TYPE_CHECKING:
        # pylint: disable=no-self-use,unused-argument
        getConfig = lambda : None
        getCSS    = lambda : None
        key       = lambda *_: None
        _figargs  = lambda *_: None
