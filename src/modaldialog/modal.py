#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from    typing                  import (Optional,  # pylint: disable=unused-import
                                        Callable, Union, Sequence, Any)
from    abc                     import ABCMeta, abstractmethod
import  re

import  bokeh.core.properties   as props
from    bokeh.models            import Model, Callback
from    utils.logconfig         import getLogger
LOGS  = getLogger()
ROUTE = 'modaldialog'

class Option(metaclass = ABCMeta):
    "Converts a text tag to an html input"
    @abstractmethod
    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        raise NotImplementedError()

    @abstractmethod
    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        raise NotImplementedError()

    def _converter(self, model, elems, cnv, storeempty = None) -> Callable:
        "returns a method which sets values in a model"
        if storeempty is None:
            def _empty(model, key):
                if elems[key]:
                    self.setvalue(model, key, None)
                elif self._cnv is str: # pylint: disable=no-member
                    self.setvalue(model, key, '')
            storeempty = _empty

        def _apply(key, val):
            if key not in elems:
                return False

            if val != '':
                try:
                    converted = cnv(val)
                except Exception as exc: # pylint: disable=broad-except
                    LOGS.exception(exc)
                else:
                    self.setvalue(model, key, converted)
            else:
                storeempty(model, key)
            return True
        return _apply

    @staticmethod
    def getvalue(mdl, keystr, default):
        "gets the value in the model"
        if isinstance(mdl, dict):
            return mdl[keystr]
        else:
            keys = keystr.split('.')
            for key in keys[:-1]:
                mdl = getattr(mdl, key)
            return getattr(mdl, keys[-1], default)

    @staticmethod
    def setvalue(mdl, keystr, val):
        "sets the value in the model"
        if isinstance(mdl, dict):
            mdl[keystr] = val
        else:
            keys = keystr.split('.')
            for key in keys[:-1]:
                mdl = getattr(mdl, key)
            setattr(mdl, keys[-1], val)

class TextOption(Option):
    "Converts a text tag to an html text input"
    def __init__(self, cnv, patt, step):
        self._cnv  = cnv
        self._patt = re.compile(r'%\((.*?)\)'+patt)
        self._step = step

    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        elems = {i[0]: i[2] == 'o' for i in self._patt.findall(body)}
        return self._converter(model, elems, self._cnv)

    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        def _replace(key, size, tpe):
            assert len(key), "keys must have a name"
            opt  = (''          if size is None else
                    'step=1'    if size == 0    else
                    'step=0.'+'0'*(size-1)+'1')

            val  = self.getvalue(model, key, None)
            if val is not None:
                opt += ' value="{}"'.format(val)

            inpt = '<input class="bk-widget-form-input" type="{}" name="{}" {}>'
            return inpt.format(tpe, key, opt)

        tpe = 'text' if self._cnv is str else 'number'
        if callable(self._step):
            fcn = lambda i: _replace(i.group(1), self._step(i), tpe)
        else:
            fcn = lambda i: _replace(i.group(1), self._step, tpe)
        return self._patt.sub(fcn, body)

class CSVOption(Option):
    "Converts a text tag to an html text input"
    def __init__(self, cnv, patt):
        super().__init__()
        split      = re.compile('[,;:]').split
        self._cnv  = lambda i: tuple(cnv(j) for j in split(i))
        self._patt = re.compile(r'%\((.*?)\)'+patt)

    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        elems = {i[0]: i[2] == 'o' for i in self._patt.findall(body)}
        return self._converter(model, elems, self._cnv)

    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        def _replace(match):
            key = match.group(1)
            assert len(key), "keys must have a name"
            val  = self.getvalue(model, key, None)
            opt  = (' value="{}"'.format(', '.join(str(i) for i in val))
                    if val is not None else '')
            opt += ' placeholder="comma separated values"'

            inpt = '<input class="bk-widget-form-input" type="text" name="{}" {}>'
            return inpt.format(key, opt)

        return self._patt.sub(_replace, body)

class DpxModal(Model):
    "Modal dialog"
    __OPTIONS          = (TextOption(int,   r'(o)*[id]',         1),
                          TextOption(float, r'(?:\.(\d))*(o)*f', lambda i: i.group(2)),
                          TextOption(str,   r'(o)*s',            None),
                          CSVOption(int,   r'(o)*csv[id]'),
                          CSVOption(float, r'(?:\.(\d))*(o)*csvf'),
                          CSVOption(str,   r'(o)*csv'))
    __css__            = [ROUTE+"/backbone.modal.css",
                          ROUTE+"/backbone.modal.theme.css"]
    __javascript__     =  ROUTE+"/underscore-min.js"
    __implementation__ = "modal.coffee"
    title              = props.String("")
    body               = props.String("")
    results            = props.Dict(props.String, props.Any)
    startdisplay       = props.Int(0)
    callback           = props.Instance(Callback)
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__handler = None # type: Optional[Callable]
        self.__running = False
        def _on_apply_cb(attr, old, new):
            if not self.__running:
                return
            self.__running = False
            if self.__handler is not None and len(new):
                self.__handler(new)
        self.on_change('results', _on_apply_cb)

    def run(self,                                       # pylint: disable=too-many-arguments
            title   : str                       = "",
            body    : Union[Sequence[str],str]  = "",
            callback: Union[Callable, Callback] = None,
            context : Callable[[str], Any]      = None,
            model                               = None):
        "runs the modal dialog"
        self.__handler = self._build_handler(callback, title, body, model, context)
        self.__running = False
        self.update(title    = title,
                    body     = self._build_body(body, model),
                    callback = self._build_callback(callback),
                    results  = {})
        self.__running      = True
        self.startdisplay   = self.startdisplay+1

    @classmethod
    def _build_body(cls, body, model):
        if isinstance(body, (tuple, list)):
            body = '<table>' + (''.join('<tr>'
                                        + ''.join('<td>'+i+'</td>' for i in j)
                                        + '</tr>'
                                        for j in body)) + '</table>'

        for tpe in cls.__OPTIONS:
            body = tpe.replace(model, body)
        return body

    @staticmethod
    def  _build_callback(callback):
        return callback if isinstance(callback, Callback) else None

    def  _build_handler(self, callback, title, # pylint: disable=too-many-arguments
                        body, model, context):
        if isinstance(callback, Callback) or model is None:
            return None

        def _hdl(itms, bdy = body):
            if isinstance(bdy, (list, tuple)):
                bdy = ' '.join(' '.join(i) for i in bdy)

            converters = [i.converter(model, bdy) for i in self.__OPTIONS]
            if context is None:
                for i in itms.items():
                    any(cnv(*i) for cnv in converters)
            else:
                with context(title):
                    for i in itms.items():
                        any(cnv(*i) for cnv in converters)
        return _hdl
