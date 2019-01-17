#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
import sys
from   inspect       import signature
from   tornado.web   import StaticFileHandler
from   .modal        import DpxModal, ROUTE

if 'app.scripting' in sys.modules:
    sys.modules['app.scripting'].addload(__name__) # type: ignore

def server(kwa):
    "adds a router to the server"
    router = ("/%s/(.*)" % ROUTE, StaticFileHandler, { "path" : "static" })
    kwa.setdefault('extra_patterns', []).append(router)

def document(doc):
    "adds the DpxModal to this doc"
    doc.add_root(DpxModal())

_PARAMS = frozenset(tuple(signature(DpxModal.run).parameters)[1:])
def dialog(doc, **_):
    "returns the DpxModal in this doc"
    for root in doc.roots:
        if isinstance(root, DpxModal):
            runargs = {i: _.pop(i) for i in _PARAMS & frozenset(_)}
            return root.run(**runargs) if len(runargs) else root

    raise RuntimeError('DpxModal is missing from the document')
