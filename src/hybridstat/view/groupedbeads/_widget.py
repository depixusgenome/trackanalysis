#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"widgets for groups of beads"
import bokeh.core.properties   as props
from bokeh.models           import Widget

from control.beadscontrol   import DataSelectionBeadController
from view.static            import route
from utils.gui              import parseints
from .._widget              import (PeakIDPathWidget, PeaksSequencePathWidget,
                                    OligoListWidget, TaskWidgetEnabler)

class DpxDiscardedBeads(Widget):
    "Toolbar model"
    __css__            = route("groupedbeads.css", "icons.css")
    __implementation__ = '_widget.coffee'
    __javascript__     = route()
    frozen      = props.Bool(True)
    discarded   = props.String('')
    accepted    = props.String('')
    seltype     = props.Bool(True)
    helpmessage = props.String('')

class DiscardedBeadsInput:
    "discarded beads"
    __widget: DpxDiscardedBeads
    def __init__(self, _, model):
        self.__model = model

    def addtodoc(self, mainview, ctrl):
        "sets-up the gui"
        bdctrl        = DataSelectionBeadController(ctrl)
        self.__widget = DpxDiscardedBeads(**self.__data(), name = 'GroupedBeads:discard')

        def _onaccepted_cb(attr, old, new):
            if not mainview.isactive():
                return

            beads = parseints(new)
            beads = set(bdctrl.allbeads) - beads
            if beads != self.__model.discardedbeads:
                with ctrl.action:
                    self.__model.discardedbeads = beads
            self.__widget.update(**self.__data())

        def _ondiscarded_cb(attr, old, new):
            if not mainview.isactive():
                return

            beads = parseints(new)
            if beads != self.__model.discardedbeads:
                with ctrl.action:
                    self.__model.discardedbeads = beads
            self.__widget.update(**self.__data())

        self.__widget.on_change('discarded',   _ondiscarded_cb)
        self.__widget.on_change('accepted',    _onaccepted_cb)
        return [self.__widget]

    def reset(self, cache):
        "resets the widget upon opening a new file, ..."
        cache[self.__widget] = self.__data()

    def __data(self):
        disc   = self.__model.discardedbeads
        bdctrl = DataSelectionBeadController(getattr(self.__model, '_ctrl'))
        acc    = set(bdctrl.allbeads) - disc
        return  dict(accepted  = ', '.join(str(i) for i in sorted(acc)),
                     discarded = ', '.join(str(i) for i in sorted(disc)))

class GroupedBeadsPlotWidgets:
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
