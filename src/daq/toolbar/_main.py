#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"bringing togethe toobar components"
from typing         import Dict, Any, Optional
import bokeh.layouts as    _layouts

from utils          import initdefaults
from view.base      import threadmethod, spawn
from view.dialog    import BaseFileDialog
from ._protocol     import (DAQProbeButton, DAQRampButton,
                            DAQManualButton, DAQNetworkButton)
from ._daqtoolbar   import DpxDAQToolbar
from ._messages     import DAQMessagesView

class DAQRecordTheme:
    "record theme"
    name            = "daq.recording"
    title           = "Record path"
    filetypes       = "h5"
    description     = 'record files'
    initialdir: Optional[str] = None

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DAQRecordFileDialog(BaseFileDialog):
    "A file dialog that adds a default save path"
    def __init__(self, **kwa):
        self._theme = DAQRecordTheme(**kwa)
        super().__init__(filetypes  = self._theme.filetypes,
                         title      = self._theme.title,
                         initialdir = self._theme.initialdir)

    def observe(self, ctrl):
        "observe the controller"
        if self._theme not in ctrl.theme:
            ctrl.theme.add(self._theme)

    async def run(self, ctrl, doc):
        "runs the dialog"
        path = await threadmethod(self.save)
        if path is not None:
            def _daqfileopen():
                with ctrl.action:
                    ctrl.theme.update(self._theme, initialdir = self.initialdir)
                    ctrl.daq.record(True, path)
            doc.add_next_tick_callback(_daqfileopen)

    def addtodoc(self, ctrl, doc, tbar, name):
        "add action to the toolbar"
        def _onclick_cb(attr, old, new):
            async def _run():
                await self.run(ctrl, doc)
            spawn(_run)

        theme                          = self._theme
        self._config.types[theme.filetypes] = (theme.description, '.'+theme.filetypes)
        tbar.on_change(name, _onclick_cb)

class DAQToolbar:
    "DAQ toolbar"
    _widget: DpxDAQToolbar
    def __init__(self, **_):
        self._messages = DAQMessagesView    (**_)
        self._ramp     = DAQRampButton      (**_)
        self._probing  = DAQProbeButton     (**_)
        self._manual   = DAQManualButton    (**_)
        self._network  = DAQNetworkButton   (**_)
        self._record   = DAQRecordFileDialog(**_)
        self._widget   = None

    def addtodoc(self, ctrl, doc):
        "add the bokeh widgets"
        self._widget    = DpxDAQToolbar(** self._messages.addtodocargs(ctrl),
                                        ** self._manual.addtodocargs(ctrl),
                                        ** self.__statusargs(ctrl))
        self._messages.addtodoc(ctrl, doc, self._widget)
        self._ramp    .addtodoc(ctrl, doc, self._widget, "ramp")
        self._probing .addtodoc(ctrl, doc, self._widget, "probing")
        self._manual  .addtodoc(ctrl, doc, self._widget, "manual")
        self._record  .addtodoc(ctrl, doc, self._widget, "record")
        self._network .addtodoc(ctrl, doc, self._widget, "network")
        self._widget.on_change("stop", lambda attr, old, new: ctrl.daq.record(False))

        mods = dict(height      = 50,
                    sizing_mode = ctrl.theme.get('main', 'sizingmode', 'fixed'))
        return _layouts.row([_layouts.widgetbox(self._widget, **mods)], **mods)

    def observe(self, ctrl):
        "observe the controller"
        self._messages.observe(ctrl)
        self._ramp    .observe(ctrl)
        self._probing .observe(ctrl)
        self._manual  .observe(ctrl)
        self._record  .observe(ctrl)
        self._network .observe(ctrl)

        @ctrl.daq.observe("record", "updateprotocol")
        def _onstoprecording(**_):
            if not self._widget:
                return
            out = self.__statusargs(ctrl)
            if ctrl.daq.config.protocol.ismanual():
                out.update(zmag  = ctrl.daq.config.protocol.zmag,
                           speed = ctrl.daq.config.protocol.speed)
            self._widget.update(**out)

    @staticmethod
    def __statusargs(ctrl) -> Dict[str, Any]:
        daq = ctrl.daq.config
        return dict(protocol  = type(daq.protocol).__name__[3:].lower(),
                    recording = daq.recording.started)
