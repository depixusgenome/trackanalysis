#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from  tornado.web   import StaticFileHandler
from  .modal        import DpxModal, ROUTE
from  .control      import ControlledDpxModal

def server(kwa):
    "adds a router to the server"
    router = ("/%s/(.*)" % ROUTE, StaticFileHandler, { "path" : "static" })
    kwa['extra_patterns'] = [router]

def dialog(doc, ctrl):
    "returns the DpxModal in this doc"
    for root in doc.roots:
        if isinstance(root, DpxModal):
            break
    else:
        root = DpxModal() if ctrl is None else ControlledDpxModal(ctrl)
        doc.add_root(root)
    return root
