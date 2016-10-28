#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default functions for waf"
import os
from typing     import Sequence, Callable
from functools  import wraps

from ._utils    import addmissing, appname
from ._python   import makemodule, checkpy, copypy, findpyext
from .          import _git as gitinfo
from .          import _cpp
from .          import _python
from waflib.Context import Context
from waflib.Build   import BuildContext

def wscripted(path) -> Sequence[str]:
    u"return subdirs with wscript in them"
    path = path.replace("\\", "/")
    if not path.endswith("/"):
        path += "/"
    return [path+x for x in os.listdir(path) if os.path.exists(path+x+"/wscript")]

def top()-> str:
    u"returns top path"
    path = __file__[:__file__.rfind("/")]
    path = path    [:path       .rfind("/")]
    return path+"/"

def output() -> str:
    u"returns build path"
    return top() + "/build"

def version() -> str:
    u"returns git tag"
    try:
        return gitinfo.version()
    except:             # pylint: disable=bare-except
        return "0.0.1"

def register(name:str, fcn:Callable[[Context], None], glob:dict):
    u"Registers a *build* command for building a single module"
    # register a command for building a single module
    type(name.capitalize()+'BuildContext', (BuildContext,),
         {'cmd': 'build_'+name , 'fun': 'build_'+name},)

    def _single(bld:BuildContext):
        u"runs a single src module"
        print("building single element: ", glob['APPNAME'])
        fcn(bld)

    glob['build_'+name] = _single

def addbuild(name:str, glob:dict):
    u"Registers a command from a child wscript"
    if '/' in name:
        glob["build_"+name[name.rfind('/')+1:]] = lambda bld: bld.recurse(name)
    else:
        glob["build_"+name] = lambda bld: bld.recurse(name)

def make(glob, **kw):
    u"sets default values to wscript global variables"
    def options(*_):
        u"does nothing"
        pass
    def configure(*_):
        u"does nothing"
        pass

    # pylint: disable=unnecessary-lambda
    toadd = dict(VERSION   = lambda: version(),
                 APPNAME   = lambda: appname(),
                 top       = lambda: ".",
                 out       = lambda: output(),
                 options   = lambda: options,
                 configure = lambda: configure,
                 build     = lambda: makemodule(glob, **kw))

    for key, fcn in toadd.items():
        if key not in glob:
            glob[key] = fcn()

    if glob['APPNAME'] not in glob:
        register(glob['APPNAME'], glob['build'], glob)

def recurse(builder, items):
    u"runs over relative path to child wscripts"
    def _wrapper(fcn):
        @wraps(fcn)
        def _wrap(bld):
            fcn(bld)
            getattr(builder, fcn.__name__)(bld)
            for item in items:
                bld.recurse(item)
        return _wrap
    return _wrapper

addmissing(locals())
