#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"widgets for groups of beads"
from copy                   import copy
from typing                 import ClassVar, Tuple, Iterator, Any
import bokeh.core.properties   as props
from bokeh                  import layouts
from bokeh.models           import Widget, TextInput

from view.static            import route
from utils.gui              import parseints
from .._model               import PoolComputationsConfig
from .._widget              import (PeakIDPathWidget, PeaksSequencePathWidget,
                                    OligoListWidget, TaskWidgetEnabler, advanced,
                                    PeakListTheme, PeakListWidget)
from ._model                import (HairpinGroupScatterModel, ConsensusHistPlotModel,
                                    ConsensusConfig, Indirection)

class DpxDiscardedBeads(Widget):
    "Toolbar model"
    __css__            = route("groupedbeads.css", "icons.css")
    __implementation__ = '_widget.coffee'
    __javascript__     = route()
    frozen        = props.Bool(True)
    hassequence   = props.Bool(False)
    discarded     = props.String('')
    discardedhelp = props.String('')
    forced        = props.String('')
    forcedhelp    = props.String('')

class DiscardedBeadsInputTheme:
    "Help messages for the widget"
    def __init__(self):
        self.name          = "groupedbeads.input"
        self.discardedhelp = "Discard beads from displays"
        self.forcedhelp    = "Force beads to a hairpin"

class DiscardedBeadsInput:
    "discarded beads"
    __widget: DpxDiscardedBeads
    def __init__(self, ctrl, model):
        self.__model = model
        self.__theme = ctrl.theme.add(DiscardedBeadsInputTheme(), False)

    def addtodoc(self, mainview, ctrl, *_):
        "sets-up the gui"
        self.__widget = DpxDiscardedBeads(
            discardedhelp = self.__theme.discardedhelp,
            forcedhelp    = self.__theme.forcedhelp,
            name          = 'HairpinGroup:filter',
            **self.__data()
        )

        def _ondiscarded_cb(attr, old, new):
            if mainview.isactive():
                beads = parseints(new)
                if beads != self.__model.discardedbeads:
                    with ctrl.action:
                        self.__model.discardedbeads = beads
                else:
                    self.__widget.update(**self.__data())

        def _onforced_cb(attr, old, new):
            if mainview.isactive():
                beads = parseints(new)
                key   = self.__model.sequencekey
                cnf   = self.__model.identification
                if beads != cnf.getforcedbeads(key):
                    with ctrl.action:
                        cnf.setforcedbeads(key, beads)
                else:
                    self.__widget.update(**self.__data())

        self.__widget.on_change('discarded',   _ondiscarded_cb)
        self.__widget.on_change('forced',      _onforced_cb)
        return [self.__widget]

    def reset(self, cache):
        "resets the widget upon opening a new file, ..."
        cache[self.__widget] = self.__data()

    def __data(self):
        forced = self.__model.identification.getforcedbeads(self.__model.sequencekey)
        return {
            'discarded': ', '.join(str(i) for i in sorted(self.__model.discardedbeads)),
            'forced':    ', '.join(str(i) for i in sorted(forced)),
            'hassequence': self.__model.identification.task is not None
        }

class Widgets:
    "peaks plot widgets"
    enabler: TaskWidgetEnabler
    _ORDER: ClassVar[Tuple[str,...]] = ()
    def _addtodoc(self, mainview, ctrl, doc, *_): # pylint: disable=unused-argument
        mode = mainview.defaultsizingmode()
        wdg  = {i: j.addtodoc(mainview, ctrl, *_) for i, j in self._widgets}
        self.enabler = TaskWidgetEnabler(wdg)
        out = layouts.widgetbox(sum((wdg[i] for i in self._ORDER), []), **mode)
        return wdg, out

    @property
    def _widgets(self) -> Iterator[Tuple[str, Any]]:
        return iter(self.__dict__.items())

    def addtodoc(self, mainview, ctrl, doc, *_):
        "creates the widget"
        return self._addtodoc(mainview, ctrl, doc, *_)[1]

    def observe(self, ctrl):
        "oberver"
        for widget in self.__dict__.values():
            if hasattr(widget, 'observe'):
                widget.observe(ctrl)

    def reset(self, cache, disable):
        "resets the widget upon opening a new file, ..."
        for key, widget in self._widgets:
            if key != 'enabler':
                widget.reset(cache)
        self.enabler.disable(cache, disable)

class HairpinGroupPlotWidgets(Widgets):
    "peaks plot widgets"
    _MDL   = HairpinGroupScatterModel
    _ORDER: ClassVar[Tuple[str,...]] = ("discarded", "seq", "oligos", "cstrpath", "advanced")
    def __init__(self, ctrl, mdl):
        self.discarded = DiscardedBeadsInput(ctrl, mdl)
        self.seq       = PeaksSequencePathWidget(ctrl, mdl)
        self.oligos    = OligoListWidget(ctrl)
        self.cstrpath  = PeakIDPathWidget(ctrl, mdl)
        self.advanced  = advanced(
            cnf       = self._MDL(),
            accessors = (PoolComputationsConfig,),
            peakstext = "Cores used for precomputations %(PoolComputationsConfig:ncpu)D"
        )(ctrl, mdl)

    def _addtodoc(self, mainview, ctrl, doc, *_):
        "creates the widget"
        out = super()._addtodoc(mainview, ctrl, doc, *_)
        if hasattr(self, 'cstrpath'):
            self.cstrpath.callbacks(ctrl, doc)
        if hasattr(self, 'advanced'):
            self.advanced.callbacks(doc)
        return out

class WidthWidgetTheme:
    "Theme for width widget"
    def __init__(self):
        self.name        = "consensus.peak.width"
        self.placeholder = "Peak kernel width (base)"
        self.format      = "{:.1f}"

class WidthWidget:
    "sets the width of the peaks"
    _config = Indirection()
    _theme  = Indirection()
    _widget : TextInput
    def __init__(self, ctrl, mdl, *_):
        self._ctrl   = ctrl
        self._mdl    = mdl
        self._config = ConsensusConfig()
        self._theme  = WidthWidgetTheme()

    def addtodoc(self, mainview, ctrl, *_):
        "sets-up the gui"
        self._widget = TextInput(placeholder = self._theme.placeholder, **self.__data())
        def _on_cb(attr, old, new):
            if not mainview.isactive():
                return

            try:
                val = float(new) if new.strip() else None
            except ValueError:
                self._widget.update(**self.__data())
                return

            instr = self._mdl.instrument
            cpy   = self._config[instr]
            if  cpy.precision == val:
                return

            cpy           = copy(cpy)
            cpy.precision = val
            with ctrl.action:
                self._ctrl.theme.update(self._config, **{instr: cpy})

        self._widget.on_change("value", _on_cb)
        return [self._widget]

    def reset(self, cache):
        "reset the widget"
        cache[self._widget].update(**self.__data())

    def __data(self):
        prec = self._config[self._mdl.instrument].precision
        return dict(value = "" if prec is None else self._theme.format.format(prec))

class ConsensusPlotWidgets(Widgets):
    "peaks plot widgets"
    _MD    = ConsensusHistPlotModel
    _ORDER = "seq", "oligos", "width"
    def __init__(self, ctrl, mdl):
        theme         = PeakListTheme(name = "consensus.peaks", height = 400)
        get           = lambda x: [x[0]+'std', x[1].replace("(", "std ("), x[2]]
        theme.columns = [
            *theme.columns[1:-4],
            ['nbeads', 'Dectection (%)', '0'],
            theme.columns[-4],
            get(theme.columns[-4]),
            theme.columns[-3],
            get(theme.columns[-3])
        ]

        self.seq      = PeaksSequencePathWidget(ctrl, mdl)
        self.oligos   = OligoListWidget(ctrl)
        self.peaks    = PeakListWidget(ctrl, mdl, theme)
        self.width    = WidthWidget(ctrl, mdl)

    def addtodoc(self, mainview, ctrl, doc, *_):
        "creates the widget"
        wdg, one = self._addtodoc(mainview, ctrl, doc, *_)
        two      = layouts.widgetbox(wdg['peaks'], **mainview.defaultsizingmode())
        return one, two
