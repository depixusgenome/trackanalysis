#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"widgets for groups of beads"
import bokeh.core.properties   as props
from bokeh.models           import Widget

from view.static            import route
from utils.gui              import parseints
from .._widget              import (PeakIDPathWidget, PeaksSequencePathWidget,
                                    OligoListWidget, TaskWidgetEnabler)

class DpxDiscardedBeads(Widget):
    "Toolbar model"
    __css__            = route("groupedbeads.css", "icons.css")
    __implementation__ = '_widget.coffee'
    __javascript__     = route()
    frozen        = props.Bool(True)
    discarded     = props.String('')
    discardedhelp = props.String('')
    forced        = props.String('')
    forcedhelp    = props.String('')

class DiscardedBeadsInputTheme:
    "Help messages for the widget"
    def __init__(self):
        self.name          = "groupedbeads.input"
        self.discardedhelp = "Discard some beads from displays"
        self.forcedhelp    = "Force beads' hairpin choice"

class DiscardedBeadsInput:
    "discarded beads"
    __widget: DpxDiscardedBeads
    def __init__(self, ctrl, model):
        self.__model = model
        self.__theme = ctrl.theme.add(DiscardedBeadsInputTheme(), False)

    def addtodoc(self, mainview, ctrl):
        "sets-up the gui"
        self.__widget = DpxDiscardedBeads(
            discardedhelp = self.__theme.discardedhelp,
            forcedhelp    = self.__theme.forcedhelp,
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
            'forced':    ', '.join(str(i) for i in sorted(forced))
        }

class HairpinGroupPlotWidgets:
    "peaks plot widgets"
    enabler: TaskWidgetEnabler
    def __init__(self, ctrl, mdl):
        "returns a dictionnary of widgets"
        self.discarded = DiscardedBeadsInput(ctrl, mdl)
        self.seq       = PeaksSequencePathWidget(ctrl, mdl)
        self.oligos    = OligoListWidget(ctrl)
        self.cstrpath  = PeakIDPathWidget(ctrl, mdl)

    def addtodoc(self, mainview, ctrl, doc):
        "creates the widget"
        wdg = {i: j.addtodoc(mainview, ctrl) for i, j in self.__dict__.items()}
        self.enabler = TaskWidgetEnabler(wdg)
        self.cstrpath.callbacks(ctrl, doc)
        return wdg

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
