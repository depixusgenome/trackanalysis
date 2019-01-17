#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from    typing                  import Optional, Callable, Union, Sequence, Any, cast
from    functools               import partial
from    abc                     import ABCMeta, abstractmethod
import  re
import  random
import  numpy                   as np

import  bokeh.core.properties   as props
from    bokeh.models            import Model, Callback
from    utils.logconfig         import getLogger
from    view.static             import ROUTE
LOGS  = getLogger()

class Option(metaclass = ABCMeta):
    "Converts a text tag to an html input"
    NAME = r'%\((?P<name>[\w\.\[\]]*)\)'
    _cnv = None
    @abstractmethod
    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        raise NotImplementedError()

    @abstractmethod
    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        raise NotImplementedError()

    def _default_empty(self, elems, model, key):
        if elems[key]:
            self.setvalue(model, key, None)
        elif self._cnv is str:
            self.setvalue(model, key, '')

    def _default_apply(self, model, elems, # pylint: disable=too-many-arguments
                       cnv, storeempty, key, val):
        if key not in elems:
            return False

        if val != '':
            try:
                converted = cnv(val)
            except Exception as exc: # pylint: disable=broad-except
                LOGS.exception(exc)
            else:
                self.setvalue(model, key, converted)
        elif isinstance(storeempty, Exception):
            raise storeempty
        else:
            storeempty(model, key)
        return True

    def _converter(self, model, elems, cnv, storeempty = None) -> Callable:
        "returns a method which sets values in a model"
        if storeempty is None:
            storeempty = partial(self._default_empty, elems)
        fcn = partial(self._default_apply, model, elems, cnv, storeempty)
        return cast(Callable, fcn)

    _INDEX = re.compile(r"(\w+)\[(\d+)\]")
    def getvalue(self, mdl, keystr, default):
        "gets the value in the model"
        if isinstance(mdl, dict):
            return mdl[keystr]

        keys = keystr.split('.')
        for key in keys[:-1]:
            match = self._INDEX.match(key)
            if match:
                mdl = getattr(mdl, match.group(1))[int(match.group(2))]
            else:
                mdl = getattr(mdl, key)

        match = self._INDEX.match(keys[-1])
        if match:
            return getattr(mdl, match.group(1), default)[int(match.group(2))]
        return getattr(mdl, keys[-1], default)

    def setvalue(self, mdl, keystr, val):
        "sets the value in the model"
        if isinstance(mdl, dict):
            mdl[keystr] = val
        else:
            keys = keystr.split('.')
            for key in keys[:-1]:
                match = self._INDEX.match(key)
                if match:
                    mdl = getattr(mdl, match.group(1))[int(match.group(2))]
                else:
                    mdl = getattr(mdl, key)

            match = self._INDEX.match(keys[-1])
            if match:
                getattr(mdl, match.group(1))[int(match.group(2))] = val
            else:
                setattr(mdl, keys[-1], val)

class ChoiceOption(Option):
    "Converts a text tag to an html check"
    _PATT = re.compile(r'%\((?P<name>[\w\.\[\]]*)\)(?P<cols>(?:\|\w+\:[^|{}<>]+)*)\|')
    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        elems = frozenset(i.group('name') for i in self._PATT.finditer(body))
        return self._converter(model, elems, lambda x: x, AssertionError())

    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        def _replace(match):
            key   = match.group('name')
            ident = key+str(random.randint(0,100000))
            out   = '<select name="{}" id="{}">'.format(key, ident)
            val   = ''
            for i in match.group('cols')[1:].split("|"):
                val = self.getvalue(model, key, i.split(":")[0])
                break

            for i in match.group('cols')[1:].split("|"):
                i    = i.split(':')
                sel  = 'selected="selected" ' if i[0] == str(val) else ""
                out += '<option {}value="{}">{}</option>'.format(sel, *i)
            return out.format(ident)+'</select>'
        return self._PATT.sub(_replace, body)

class CheckOption(Option):
    "Converts a text tag to an html check"
    _PATT = re.compile(Option.NAME+'b')
    @staticmethod
    def __cnv(val):
        if val in ('on', True):
            return True
        if val in ('off', False):
            return False
        raise ValueError()

    def converter(self, model, body:str) -> Callable:
        "returns a method which sets values in a model"
        elems = frozenset(i.group('name') for i in self._PATT.finditer(body))
        return self._converter(model, elems, self.__cnv, AssertionError())

    def replace(self, model, body:str) -> str:
        "replaces a pattern by an html tag"
        def _replace(match):
            key = match.group('name')
            assert len(key), "keys must have a name"
            val = 'checked' if bool(self.getvalue(model, key, False)) else ''
            return ('<input type="checkbox" class="bk-bs-checkbox '
                    'bk-widget-form-input" name="{}" {} />'
                    .format(key, val))

        return self._PATT.sub(_replace, body)

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
        def _replace(info, tpe):
            key = info['name']
            assert len(key), "keys must have a name"

            opt = self.__step(info)
            if info.get("fmt", "s").upper() == info.get("fmt", "s"):
                opt += " min=0"

            opt += self.__value(model, key, info)
            if info.get('width', None):
                opt += f' style="width: {info["width"]}px;"'

            inpt = '<input class="bk-widget-form-input" type="{}" name="{}" {}>'
            return inpt.format(tpe, key, opt)

        tpe = 'text' if self._cnv is str else 'number'
        fcn = lambda i: _replace(i.groupdict(), tpe)
        return self._patt.sub(fcn, body)

    def __step(self, info) -> str:
        return (
            ''                        if self._step is None          else
            'step='+str(self._step)   if isinstance(self._step, int) else
            ''                        if info[self._step] is None    else
            'step=0.'+'0'*(int(info[self._step])-1)+'1'
        )

    def __value(self, model, key, info) -> str:
        val = self.getvalue(model, key, None)
        if val in (None, ""):
            return ""

        if isinstance(self._step, int):
            val = np.around(val, int(self._step))
        elif info.get(self._step, None) is not None:
            val = np.around(val, int(info[self._step]))
        return ' value="{}"'.format(val)

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
            if match.group('width'):
                opt += f' style="width: {match.group("width")}px;"'

            inpt = '<input class="bk-widget-form-input" type="text" name="{}" {}>'
            return inpt.format(key, opt)

        return self._patt.sub(_replace, body)

class DpxModal(Model):
    "Modal dialog"
    _PREC              = r'(?:\.(?P<prec>\d*))?'
    _OPT               = r'(?P<opt>o)?'
    __OPTIONS          = (CheckOption(),
                          TextOption(int,   _OPT+r'(?P<fmt>[idID])',     0),
                          TextOption(float, _PREC+_OPT+r'(?P<fmt>[fF])', 'prec'),
                          TextOption(str,   _OPT+r'(?P<width>\d*)s',    None),
                          CSVOption(int,    _OPT+r'(?P<width>\d*)csv[id]'),
                          CSVOption(float,  _OPT+r'csvf'),
                          CSVOption(str,    _OPT+r'csv'),
                          ChoiceOption())
    __css__            = [ROUTE+"/backbone.modal.css?v=2",
                          ROUTE+"/backbone.modal.theme.css"]
    __javascript__     = [ROUTE+"/underscore-min.js",
                          ROUTE+"/jquery.min.js"]
    __implementation__ = "modal.coffee"
    title              = props.String("")
    body               = props.String("")
    buttons            = props.String("")
    results            = props.Dict(props.String, props.Any)
    submitted          = props.Int(0)
    startdisplay       = props.Int(0)
    callback           = props.Instance(Callback)
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__handler: Optional[Callable] = None
        self.__running = False
        self.__always  = False

        self.on_change('submitted', self._onsubmitted_cb)
        self.on_change('results',   self._onresults_cb)

    def _onresults_cb(self, attr, old, new):
        if self.__running and not self.__always and len(new) and self.__handler:
            self.__handler(new)

    def _onsubmitted_cb(self, attr, old, new):
        if self.__running and self.__always and self.__handler:
            self.__handler(self.results)

        self.__running = False

    def run(self,                                       # pylint: disable=too-many-arguments
            title   : str                       = "",
            body    : Union[Sequence[str],str]  = "",
            callback: Union[Callable, Callback] = None,
            context : Callable[[str], Any]      = None,
            model                               = None,
            buttons                             = "",
            always                              = False):
        "runs the modal dialog"
        self.__handler = self._build_handler(callback, title, body, model, context)
        self.__always  = always
        self.__running = False
        self.update(title    = title,
                    body     = self._build_body(body, model),
                    callback = self._build_callback(callback),
                    buttons  = buttons,
                    results  = {})
        self.__running      = True
        self.startdisplay   = self.startdisplay+1

    @staticmethod
    def _build_elem(val):
        if isinstance(val, tuple):
            return f'<td style="{val[0]}">'+val[1]+'</td>'
        return f'<td>'+val+'</td>'

    @classmethod
    def _build_body(cls, body, model):
        if isinstance(body, (tuple, list)):
            if len(body) == 0:
                return ""
            if hasattr(body[0], 'tohtml'):
                body = body[0].tohtml(body)
            else:
                body = '<table>' + (''.join('<tr>'
                                            + ''.join(cls._build_elem(i) for i in j)
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
                if len(bdy) and hasattr(bdy[0], 'body'):
                    bdy = sum((tuple(i.body) for i in bdy), ())
                bdy = ' '.join(' '.join(k if isinstance(k, str) else k[1] for k in i)
                               for i in bdy)

            converters = [i.converter(model, bdy) for i in self.__OPTIONS]
            ordered    = sorted(itms.items(), key = lambda i: bdy.index('%('+i[0]))
            if context is None:
                for i in ordered:
                    any(cnv(*i) for cnv in converters)
            else:
                with context(title):
                    for i in ordered:
                        any(cnv(*i) for cnv in converters)
        return _hdl
