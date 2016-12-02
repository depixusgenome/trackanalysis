#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"controls keypress actions"
from typing                import Callable, Optional # pylint: disable=unused-import
from bokeh.core.properties import String, Int
from bokeh.model           import Model

class KeyPressManager(Model):
    u"controls keypress actions"
    value              = String("")
    count              = Int(0)
    __implementation__ = u"""
        p         = require "core/properties"
        BokehView = require "core/bokeh_view"
        Model     = require "model"
        $         = require "jquery"
        
        class DpxKeyEventView extends BokehView
            initialize: (options) ->
                super(options)
                console.log("keyevt: rendering")
                $(document).keydown((e) => @_key_down(e))

            _key_down: (evt) ->
                if evt.target != document.body then return

                val = ""

                cnv = alt: 'Alt', shift: 'Shift', ctrl: 'Control', meta: 'Meta'
                for name, kw of cnv
                    if evt[name+'Key']
                         val += "#{kw}-"

                if val == (evt.key+'-')
                    val = evt.key
                else
                    val += evt.key

                @model.value = val
                @model.count = @model.count+1
        
        class DpxKeyEvent extends Model
            default_view: DpxKeyEventView
            type:"DpxKeyEvent"
        
            @define { value: [p.String, ""], count: [p.Int, 0] }
        
        module.exports =
          Model: DpxKeyEvent
          View:  DpxKeyEventView
        """

    def __init__(self, **kwargs):
        super().__init__()
        self._keys = kwargs.pop('keys', dict()) # type: Dict[str,Callable]
        self._ctrl = kwargs.pop('ctrl', None)   # type: Optional[Controller]
        self.addKeyPress(**kwargs)

    def close(self):
        u"Removes the controller"
        self.popKeyPress(all)
        self._ctrl = None

    def onKeyPress(self):
        u"Method to be connected to the gui"
        items = self._ctrl.getGlobal('config')
        for name, fcn in self._keys.items():
            if self.value == items[name].value:
                fcn()
                break

    def addKeyPress(self, *args, **kwargs):
        u"""
        Sets-up keypress methods.

        if args is one string, then that string is used as a prefix to all
        keys in kwargs.

        Otherwise args must be valid arguments to dict.update.
        """
        if len(args) == 1 and isinstance(args[0], str) and len(kwargs):
            kwargs = {args[0]+'.'+name: val for name, val in kwargs.items()}
        else:
            kwargs.update(args)

        self._keys.update(kwargs)
        if not all(isinstance(i, Callable) for i in kwargs.values()) :
            raise TypeError("keypress values should be callable")

    def popKeyPress(self, *args):
        u"removes keypress method"
        if len(args) == 1 and args[0] is all:
            self._keys = dict()

        else:
            for arg in args:
                self._keys.pop(arg, None)

    def getroots(self):
        u"returns object root"
        self.on_change("count", lambda attr, old, value: self.onKeyPress())
        return self,
