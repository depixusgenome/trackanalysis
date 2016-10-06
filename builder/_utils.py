#! /usr/bin/env python
# encoding: utf-8
u"Default utils for waf"
import inspect
from typing         import Iterator, Callable, Iterable, Union, cast
from types          import ModuleType, FunctionType
from functools      import wraps

from waflib.Context import Context

YES = type('YES', (object,), dict(__doc__ = u"Used as a typed enum"))()

def _add(fcn, name : str):
    fname = getattr(fcn, '__func__', fcn).__name__
    return type(fname[0].upper()+fname[1:]+'Make', (Make,), {name: fcn})

def appname(iframe: int  = None) -> str:
    u"returns directory"
    if iframe is None:
        mymod  = __file__.replace('\\', '/')
        mymod  = mymod[:mymod.rfind('/')]
        myroot = mymod[:mymod.rfind('/')]
        for frame in inspect.getouterframes(inspect.currentframe()):
            if frame.filename.startswith('<') or mymod in frame.filename:
                continue
            if myroot not in frame.filename:
                continue
            fname = frame.filename
            break
    else:
        fname = inspect.getouterframes(inspect.currentframe())[iframe].filename
    fname = fname.replace('\\', '/')
    fname = fname[:fname.rfind('/')]
    return fname[fname.rfind('/')+1:]

class Make(object):
    u"base class for a given functionnality"
    IS_MAKE = YES

    @classmethod
    def options(cls, opt):
        u"Finds all configure methods in child class members"
        run(opt, 'options', makes(cls))

    @classmethod
    def configure(cls, cnf):
        u"Finds all configure methods in child class members"
        run(cnf, 'configure', makes(cls))

    @classmethod
    def build(cls, bld):
        u"Finds all build methods in child class members"
        run(bld, 'build', makes(cls))

def run(item:Context, name:str, elems:Iterable):
    u"runs a method to all elements"
    for cls in elems:
        getattr(cls, name, lambda _: None)(item)

def runall(fcn: Callable[[Context], None]):
    u"""
    decorator for calling all Make objects after the decorated function.

    usage:

    >> class MyMake(Make):
    >>    @staticmethod
    >>    def configure(cnf):
    >>       print("this happens later")
    >>
    >> @runall
    >> def configure(cnf):
    >>    print("this happens first")
    """
    if not isinstance(fcn, FunctionType):
        raise TypeError('{} should be a function'.format(fcn))

    mod = inspect.getmodule(fcn)

    @wraps(cast(Callable, fcn))
    def _wrapper(cnf:Context):
        fcn(cnf)
        run(cnf, fcn.__name__, makes(mod))

    return _wrapper

def makes(elems:Union[Iterable,dict,type,ModuleType]) -> Iterator[type]:
    u"gets a list of Makes"
    if isinstance(elems, (type, ModuleType)):
        elems = iter(cls for _, cls in inspect.getmembers(elems))

    elif hasattr(elems, 'items'):
        elems = iter(cls for _, cls in cast(dict, elems).items())

    for cls in elems:
        if cls is not Make and getattr(cls, 'IS_MAKE', None) is YES:
            yield cls

def addconfigure(fcn):
    u"adds a configure element to a context"
    return _add(fcn, 'configure')

def addbuild(fcn):
    u"adds a build element to a context"
    return _add(fcn, 'build')

def addoptions(fcn):
    u"adds an option element to a context"
    return _add(fcn, 'options')

def addmissing(glob, tt = None):
    u"adds functions 'load', 'options', 'configure', 'build' if missing from a module"
    items = tuple(makes(iter(cls for _, cls in glob.items())))

    def load(opt:Context):
        u"applies load from all basic items"
        opt.load(' '.join(getattr(cls, 'loads', lambda:'')() for cls in items))

    def options(opt:Context):
        u"applies options from all basic items"
        glob.get('load', lambda _: None)(opt)
        run(opt, 'options', items)

    def configure(cnf:Context):
        u"applies configure from all basic items"
        glob.get('load', lambda _: None)(cnf)
        run(cnf, 'configure', items)

    def build(bld:Context):
        u"applies build from all basic items"
        run(bld, 'build', items)

    for val in (load, options, configure, build):
        val.__module__ = glob['__name__']
        glob.setdefault(val.__name__, val)
