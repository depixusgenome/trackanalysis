#!/usr/bin/env python
# encoding: utf-8
u"Default functions for waf"
import os
import inspect
from typing     import Sequence

from ._utils    import addmissing
from ._python   import makemodule
from .          import _git as gitinfo
from .          import _cpp
from .          import _python

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

def version(_: int  = 1) -> str:
    u"returns git tag"
    try:    return gitinfo.version()
    except: return "0.0.1"

def appname(frame: int  = 1) -> str:
    u"returns directory"
    fname = inspect.getouterframes(inspect.currentframe())[frame].filename
    fname = fname.replace('\\', '/')
    fname = fname[:fname.rfind('/')]
    return fname[fname.rfind('/')+1:]

def make(glob, **kw):
    u"sets default values to wscript global variables"
    def options(*_):
        u"does nothing"
        pass
    def configure(*_):
        u"does nothing"
        pass

    toadd = dict(VERSION   = version(2),
                 APPNAME   = appname(2),
                 top       = ".",
                 out       = output(),
                 options   = options,
                 configure = configure,
                 build     = makemodule(glob, **kw))

    for key, fcn in toadd.items():
        if key not in glob:
            glob[key] = fcn

addmissing(locals())
