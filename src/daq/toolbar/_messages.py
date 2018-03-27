#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
import time

from   bokeh.document     import Document
from   bokeh.io           import curdoc

from   utils              import initdefaults
from   utils.logconfig    import getLogger

LOGS  = getLogger(__name__)

class DAQMessageTheme:
    "Message theme"
    _SIZ    = 'heigth: 28px; margin-top: 0px;'
    name    = "message"
    period  = 50
    width   = 350
    busy    = "Please wait ..."
    types   = dict(normal  = '<p style="%s">{}</p>' % _SIZ,
                   warning = '<p style="%s color:blue;">{}</p>' % _SIZ,
                   error   = '<p style="%s color:red;"> {}</p>' % _SIZ,
                   busy    = u'Please wait ...')
    timeout = dict(normal  = 1.,
                   error   = 50.,
                   warning = 50.)

    del _SIZ

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DAQMessageDisplay:
    "Message display"
    name    = "message"
    message = ""
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DAQMessagesView:
    "Everything related to messages"
    def __init__(self, ctrl, tbar, **_):
        self._theme        = DAQMessageTheme(**_)
        self._display      = DAQMessageDisplay(**_)
        self._tbar         = tbar
        self._last:list    = [None, None, self._theme.timeout['normal']]
        self._doc:Document = None
        if ctrl:
            self.observe(ctrl)

    def observe(self, ctrl):
        "initializes globals"
        if self._theme in ctrl:
            return

        ctrl.theme.add(self._theme)
        ctrl.display.add(self._display)
        busy  = self._theme.busy, 'normal'

        @ctrl.display.observe
        def _onstartaction(recursive = None):      # pylint: disable=unused-variable
            if not recursive:
                self._settext(busy)

        @ctrl.display.observe
        def _onstartcomputation(recursive = None): # pylint: disable=unused-variable
            if recursive:
                return
            val = self._display.message
            if val is None or (isinstance(val, tuple) and val[1] == 'normal'):
                self._settext(busy)

        @ctrl.display.observe("stopaction", "stopcomputation")
        def _observer(recursive  = None,           # pylint: disable=unused-variable
                      value      = None,
                      catcherror = None, **_):
            if not recursive and value is not None:
                LOGS.info('stop')
                ctrl.display.update(self._display, message = value)
                catcherror[0] = getattr(ctrl, 'CATCHERROR', True)

        @ctrl.display.observe
        def _onmessage(old = None, **_): # pylint: disable=unused-variable
            if 'message' in old:
                self._settext(self._display.message)

    def addtodoc(self, tbar, doc, _):
        "add to doc"
        self._tbar = tbar
        self._doc  = doc
        self._last = [None, None, self._theme.timeout['normal']]
        def _setmsg():
            if self._last[0] is None:
                return

            if self._last[0] != '':
                self._tbar.message = self._last[0]
                self._last[0] = ''
                self._last[1] = time.time()+self._last[2]

            elif self._last[1] < time.time():
                self._last[0]      = None
                self._tbar.message = ''
        doc.add_periodic_callback(_setmsg, self._theme.period)

    def addtodocargs(self, _):
        "return args for the toolbar"
        return dict(message = self._display.message)

    def _settext(self, text):
        text = getattr(text, 'value', text)
        if text is None:
            return

        templ = self._theme.types
        if isinstance(text, Exception):
            args = getattr(text, 'args', tuple())
            if len(args) == 1:
                args = args[0], 'error'
            elif len(args) != 2:
                args = text,    'error'
            elif args[1] not in templ:
                args = str(args), 'error'
        else:
            args = text

        val = templ[str(args[1])].format(str(args[0])
                                         .replace('<', '&lt')
                                         .replace('>', '&gt'))
        if args[1] == 'error':
            LOGS.error(str(args[0]))
        elif args[1] == 'warning':
            LOGS.warning(str(args[0]))

        timeout       = self._theme.timeout
        self._last[0] = val
        self._last[1] = time.time()+timeout.get(args[1], timeout['normal'])
        self._last[2] = timeout.get(args[1], timeout['normal'])
        if curdoc() is self._doc:
            try:
                self._tbar.message = val
                return
            except RuntimeError:
                pass
