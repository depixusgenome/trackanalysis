#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from    typing                  import (Optional,  # pylint: disable=unused-import
                                        Callable, Union, Sequence)
from    abc                     import ABCMeta, abstractmethod
import  re
import  numpy as np

import  bokeh.core.properties   as props
from    bokeh.models            import Model, Callback

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

class TextOption(Option):
    "Converts a text tag to an html text input"
    def __init__(self, cnv, patt, step):
        self._cnv  = cnv
        self._patt = re.compile(r'%\((.*?)\)'+patt)
        self._step = step

    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        def _replace(key, size, tpe):
            assert len(key), "keys must have a name"
            opt  = (''          if size is None else
                    'step=1'    if size == 0    else
                    'step=0.'+'0'*(size-1)+'1')
            if np.isscalar(getattr(model, key, None)):
                opt += ' value={}'.format(getattr(model, key))

            inpt = '<input class="bk-widget-form-input" type="{}" name="{}" {}>'
            return inpt.format(tpe, key, opt)

        tpe = 'text' if self._cnv is str else 'number'
        if callable(self._step):
            fcn = lambda i: _replace(i.group(1), self._step(i), tpe)
        else:
            fcn = lambda i: _replace(i.group(1), self._step, tpe)
        return self._patt.sub(fcn, body)

    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        elems = {i[0]: i[2] == 'o' for i in self._patt.findall(body)}
        cnv   = self._cnv
        def _apply(key, val):
            opt = elems.get(key, None)
            if opt is None:
                return False

            if val != '' :
                setattr(model, key, cnv(val))
            elif opt:
                setattr(model, key, None)
            elif cnv is str:
                setattr(model, key, '')
            return True
        return _apply

class DpxModal(Model):
    "Modal dialog"
    __INSTANCE         = None # type: Optional[DpxModal]
    __OPTIONS          = (TextOption(int,   r'(o)*[id]',         1),
                          TextOption(float, r'(?:\.(\d))*(o)*f', lambda i: i.group(2)),
                          TextOption(str,   r'(o)*s',            None))
    __css__            = ["consts/backbone.modal.css",
                          "consts/backbone.modal.theme.css"]
    __javascript__     = "consts/underscore-min.js"
    __implementation__ = "modal.coffee"
    title              = props.String("")
    body               = props.String("")
    results            = props.Dict(props.String, props.Any)
    startdisplay       = props.Int(0)
    callback           = props.Instance(Callback)
    def __init__(self, **kwa):
        assert self.__INSTANCE is None, "Don't call init again"
        type(self).__INSTANCE = self # pylint: disable=protected-access

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

    @classmethod
    def run(cls,
            title   : str                       = "",
            body    : Union[Sequence[str],str]  = "",
            callback: Union[Callable, Callback] = None,
            model                               = None):
        "runs the modal dialog"
        # pylint: disable=protected-access
        assert cls.__INSTANCE is not None, "Must first add this to the doc as a root"
        return cls.__INSTANCE.__run(title, body, callback, model)

    def __run(self,
              title   : str,
              body    : Union[Sequence[str],str],
              callback: Union[Callable, Callback],
              model):
        "runs the modal dialog"
        self.__handler = self.__build_handler(callback, body, model)
        self.__running = False
        self.update(title    = title,
                    body     = self.__build_body(body, model),
                    callback = self.__build_callback(callback),
                    results  = {})
        self.__running      = True
        self.startdisplay   = self.startdisplay+1

    @classmethod
    def __build_body(cls, body, model):
        if isinstance(body, (tuple, list)):
            body = '<table>' + (''.join('<tr>'
                                        + ''.join('<td>'+i+'</td>' for i in j)
                                        + '</tr>'
                                        for j in body)) + '</table>'

        for tpe in cls.__OPTIONS:
            body = tpe.replace(model, body)
        return body

    @staticmethod
    def  __build_callback(callback):
        return callback if isinstance(callback, Callback) else None

    @classmethod
    def  __build_handler(cls, callback, body, model):
        if isinstance(callback, Callback):
            return None

        if model is not None:
            def _hdl(itms, __body__ = body):
                if isinstance(__body__, (list, tuple)):
                    __body__ = ' '.join(' '.join(i) for i in __body__)

                converters = [i.converter(model, __body__) for i in cls.__OPTIONS]
                for i in itms.items():
                    any(cnv(*i) for cnv in converters)
            return _hdl
        return None
