#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"gui related utils"

import re
import sys
import os
import pathlib
import subprocess
from   functools   import wraps
from   inspect     import ismethod as _ismeth, isfunction as _isfunc, getmembers
from   enum        import Enum
from   typing      import Union, Optional  # pylint: disable=unused-import
from   .inspection import ismethod

def coffee(apath:'Union[str,pathlib.Path]', name:'Optional[str]' = None, **kwa) -> str:
    u"returns the javascript implementation code"
    path = pathlib.Path(apath)
    if name is not None:
        path = path.parent / name # type: ignore

    src = pathlib.Path(path.with_suffix(".coffee")).read_text()
    for name, val in kwa.items():
        src = src.replace("$$"+name, val)
    return src.replace('$$', '')

class MetaMixin(type):
    u"""
    Mixes base classes together.

    Mixin classes are actually composed. That way there are fewer name conflicts
    """
    def __new__(mcs, clsname, bases, nspace, **kw):
        mixins = kw['mixins']
        def setMixins(self, instances = None, initargs = None):
            u"sets-up composed mixins"
            for base in mixins:
                name =  base.__name__.lower()
                if instances is not None and name in instances:
                    setattr(self, name, instances[name])
                elif getattr(self, name, None) is None:
                    if initargs is not None:
                        setattr(self, name, base(**initargs))
                    else:
                        setattr(self, name, base())

        nspace['setMixins'] = setMixins

        def getMixin(self, base):
            u"returns the mixin associated with a class"
            return getattr(self, base.__name__.lower(), None)

        nspace['getMixin'] = getMixin

        init = nspace.get('__init__', lambda *_1, **_2: None)
        def __init__(self, **kwa):
            init(self, **kwa)
            for base in bases:
                base.__init__(self, **kwa)
            self.setMixins(mixins, initargs = kwa)

        nspace['__init__'] = __init__
        nspace.update(mcs.__addaccesses(mixins, nspace, kw))

        mnames = tuple(base.__name__.lower() for base in mixins)
        nspace['_mixins'] = property(lambda self: (getattr(self, i) for i in mnames))

        dummy = lambda *_1, **_2: tuple()

        def _callmixins(self, name, *args, **kwa):
            for mixin in getattr(self, '_mixins'):
                getattr(mixin, name, dummy)(*args, **kwa)
        nspace['_callmixins'] = _callmixins

        def _yieldovermixins(self, name, *args, **kwa):
            for mixin in getattr(self, '_mixins'):
                yield from getattr(mixin, name, dummy)(*args, **kwa)
        nspace['_yieldovermixins'] = _yieldovermixins

        return type(clsname, bases, nspace)

    @classmethod
    def __addaccesses(mcs, mixins, nspace, kwa):
        match   = re.compile(kwa.get('match', r'^[a-z][a-zA-Z0-9]+$')).match
        members = dict()
        for base in mixins:
            for name, fcn in getmembers(base):
                if match(name) is None or name in nspace:
                    continue
                members.setdefault(name, []).append((base, fcn))

        for name, fcns in members.items():
            if len(set(j for _, j in fcns)) > 1:
                if not kwa.get('selectfirst', False):
                    raise NotImplementedError("Multiple funcs: "+str(fcns))

            base, fcn = fcns[0]
            if _ismeth(fcn) or (_isfunc(fcn) and not ismethod(fcn)):
                yield (name, mcs.__createstatic(fcn))
            elif _isfunc(fcn):
                yield (name, mcs.__createmethod(base, fcn))
            elif isinstance(fcn, Enum):
                yield (name, fcn)
            elif isinstance(fcn, property):
                yield (name, mcs.__createprop(base, fcn))

    @staticmethod
    def __createstatic(fcn):
        @wraps(fcn)
        def _wrap(*args, **kwa):
            return fcn(*args, **kwa)
        return staticmethod(_wrap)

    @staticmethod
    def __createmethod(base, fcn, ):
        cname = base.__name__.lower()
        @wraps(fcn)
        def _wrap(self, *args, **kwa):
            return fcn(getattr(self, cname), *args, **kwa)
        return _wrap

    @staticmethod
    def __createprop(base, prop):
        fget = (None if prop.fget is None
                else lambda self: prop.fget(self.getMixin(base)))
        fset = (None if prop.fset is None
                else lambda self, val: prop.fset(self.getMixin(base), val))
        fdel = (None if prop.fdel is None
                else lambda self: prop.fdel(self.getMixin(base)))

        return property(fget, fset, fdel, prop.__doc__)

def startfile(filepath:str):
    u"launches default application for given file"
    if sys.platform.startswith('darwin'):
        subprocess.Popen(('open', filepath))
    elif os.name == 'nt':
        old      = os.path.abspath(os.path.curdir)
        filepath = os.path.abspath(filepath)
        os.chdir(os.path.dirname(filepath))
        os.startfile(os.path.split(filepath)[-1])  # pylint: disable=no-member
        os.chdir(old)
    elif os.name == 'posix':
        subprocess.Popen(('xdg-open', filepath))
