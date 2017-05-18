#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from  inspect       import signature
from  tornado.web   import StaticFileHandler
from  .modal        import DpxModal, ROUTE

def server(kwa):
    "adds a router to the server"
    router = ("/%s/(.*)" % ROUTE, StaticFileHandler, { "path" : "static" })
    kwa['extra_patterns'] = [router]

_PARAMS = tuple(signature(DpxModal.run).parameters)[1:]
def dialog(doc, **_):
    "returns the DpxModal in this doc"
    runargs = {i: _.pop(i) for i in _PARAMS}
    for root in doc.roots:
        if isinstance(root, DpxModal):
            break
    else:
        root = DpxModal(**_)
        doc.add_root(root)
    if len(runargs):
        return root.run(**runargs)
    else:
        return root
