#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"widgets for groups of beads"
from typing                 import ClassVar, Tuple
import bokeh.core.properties   as props
from bokeh                  import layouts
from bokeh.models           import Widget

from view.static            import route
from utils.gui              import parseints
from .._model               import PoolComputationsConfig
from .._widget              import (PeakIDPathWidget, PeaksSequencePathWidget,
                                    OligoListWidget, TaskWidgetEnabler, advanced,
                                    PeakListTheme, PeakListWidget)
from ._model                import HairpinGroupScatterModel, ConsensusHistPlotModel

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

class HairpinGroupPlotWidgets:
    "peaks plot widgets"
    enabler: TaskWidgetEnabler
    _MDL   = HairpinGroupScatterModel
    _ORDER: ClassVar[Tuple[str,...]] = ("discarded", "seq", "oligos", "cstrpath", "advanced")
    def __init__(self, ctrl, mdl):
        if 'discarded' in self._ORDER:
            self.discarded = DiscardedBeadsInput(ctrl, mdl)
        if 'seq' in self._ORDER:
            self.seq       = PeaksSequencePathWidget(ctrl, mdl)
        if 'oligos' in self._ORDER:
            self.oligos    = OligoListWidget(ctrl)
        if 'cstrpath' in self._ORDER:
            self.cstrpath  = PeakIDPathWidget(ctrl, mdl)

        if 'advanced' in self._ORDER:
            self.advanced  = advanced(
                cnf       = self._MDL(),
                accessors = (PoolComputationsConfig,),
                peakstext = "Cores used for precomputations %(PoolComputationsConfig:ncpu)D"
            )(ctrl, mdl)

    def addtodoc(self, mainview, ctrl, doc, *_):
        "creates the widget"
        mode = mainview.defaultsizingmode()
        wdg  = {i: j.addtodoc(mainview, ctrl, *_) for i, j in self.__dict__.items()}
        self.enabler = TaskWidgetEnabler(wdg)
        if hasattr(self, 'cstrpath'):
            self.cstrpath.callbacks(ctrl, doc)
        if hasattr(self, 'advanced'):
            self.advanced.callbacks(doc)
        return layouts.widgetbox(sum((wdg[i] for i in self._ORDER), []), **mode)

    def observe(self, ctrl):
        "oberver"
        for widget in self.__dict__.values():
            if hasattr(widget, 'observe'):
                widget.observe(ctrl)

    def reset(self, cache, disable):
        "resets the widget upon opening a new file, ..."
        for key, widget in self.__dict__.items():
            if key != 'enabler':
                widget.reset(cache)
        self.enabler.disable(cache, disable)

class ConsensusPlotWidgets(HairpinGroupPlotWidgets):
    "peaks plot widgets"
    _MD    = ConsensusHistPlotModel
    _ORDER = "seq", "oligos", "advanced", "peaks"
    def __init__(self, ctrl, mdl):
        super().__init__(ctrl, mdl)
        theme         = PeakListTheme(name = "consensus.peaks", height = 200)
        theme.columns = theme.columns[1:-2]
        self.peaks    = PeakListWidget(ctrl, mdl, theme)
