#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from    typing                  import (Optional,  # pylint: disable=unused-import
                                        Callable, Union, Sequence, Any, cast)
from    functools               import partial
from    abc                     import ABCMeta, abstractmethod
import  re

import  bokeh.core.properties   as props
from    bokeh.models            import Model, Callback
from    utils.logconfig         import getLogger
LOGS  = getLogger()
ROUTE = 'modaldialog'

class Option(metaclass = ABCMeta):
    "Converts a text tag to an html input"
    NAME = r'%\((?P<name>[\w\.]*)\)'
    @abstractmethod
    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        raise NotImplementedError()

    @abstractmethod
    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        raise NotImplementedError()

    @classmethod
    def _default_empty(cls, elems, model, key):
        if elems[key]:
            cls.setvalue(model, key, None)
        elif cls._cnv is str: # pylint: disable=no-member
            cls.setvalue(model, key, '')

    @classmethod
    def _default_apply(cls, model, elems, # pylint: disable=too-many-arguments
                       cnv, storeempty, key, val):
        if key not in elems:
            return False

        if val != '':
            try:
                converted = cnv(val)
            except Exception as exc: # pylint: disable=broad-except
                LOGS.exception(exc)
            else:
                cls.setvalue(model, key, converted)
        elif isinstance(storeempty, Exception):
            raise storeempty
        else:
            storeempty(model, key)
        return True

    @classmethod
    def _converter(cls, model, elems, cnv, storeempty = None) -> Callable:
        "returns a method which sets values in a model"
        if storeempty is None:
            storeempty = partial(cls._default_empty, elems)
        fcn = partial(cls._default_apply, model, elems, cnv, storeempty)
        return cast(Callable, fcn)

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

class CheckOption(Option):
    "Converts a text tag to an html check"
    _PATT = re.compile(Option.NAME+'b')
    @staticmethod
    def __cnv(val):
        return val == 'on'

    @classmethod
    def converter(cls, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        elems = frozenset(i.group('name') for i in cls._PATT.finditer(body))
        return cls._converter(model, elems, bool, AssertionError())

    @classmethod
    def replace(cls, model, body:str) -> str:
        "replaces a pattern by an html tag"
        def _replace(match):
            key = match.group('name')
            assert len(key), "keys must have a name"
            val = 'checked' if bool(cls.getvalue(model, key, False)) else ''
            return '<input type="checkbox" name="{}" {} />'.format(key, val)

        return cls._PATT.sub(_replace, body)

class TextOption(Option):
    "Converts a text tag to an html text input"
    def __init__(self, cnv, patt, step):
        self._cnv  = cnv
        self._patt = re.compile(self.NAME+patt)
        self._step = step

    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        elems = {i.group('name'): i.group('opt') == 'o' for i in self._patt.finditer(body)}
        return self._converter(model, elems, self._cnv)

    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        def _replace(key, size, tpe):
            assert len(key), "keys must have a name"
            opt  = (''          if size is None   else
                    'step=1'    if int(size) == 0 else
                    'step=0.'+'0'*(int(size)-1)+'1')

            val  = self.getvalue(model, key, None)
            if val is not None:
                opt += ' value="{}"'.format(val)

            inpt = '<input class="bk-widget-form-input" type="{}" name="{}" {}>'
            return inpt.format(tpe, key, opt)

        tpe = 'text' if self._cnv is str else 'number'
        if callable(self._step):
            fcn = lambda i: _replace(i.group('name'), self._step(i), tpe)
        else:
            fcn = lambda i: _replace(i.group('name'), self._step, tpe)
        return self._patt.sub(fcn, body)

class CSVOption(Option):
    "Converts a text tag to an html text input"
    def __init__(self, cnv, patt):
        super().__init__()
        split      = re.compile('[,;:]').split
        self._cnv  = lambda i: tuple(cnv(j) for j in split(i))
        self._patt = re.compile(self.NAME+patt)

    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        elems = {i.group('name'): i.group('opt') == 'o' for i in self._patt.finditer(body)}
        return self._converter(model, elems, self._cnv)

    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        def _replace(match):
            key = match.group('name')
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
    _PREC              = r'(?:\.(?P<prec>\d*))?'
    _OPT               = r'(?P<opt>o)?'
    __OPTIONS          = (CheckOption(),
                          TextOption(int,   _OPT+r'[id]',    0),
                          TextOption(float, _PREC+_OPT+r'f', lambda i: i.group('prec')),
                          TextOption(str,   _OPT+r's',       None),
                          CSVOption(int,    _OPT+r'csv[id]'),
                          CSVOption(float,  _OPT+r'csvf'),
                          CSVOption(str,    _OPT+r'csv'))
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
            ordered    = sorted(itms.items(), key = lambda i: bdy.index('%('+i[0]+')'))
            print(ordered)
            if context is None:
                for i in ordered:
                    any(cnv(*i) for cnv in converters)
            else:
                with context(title):
                    for i in ordered:
                        any(cnv(*i) for cnv in converters)
        return _hdl
