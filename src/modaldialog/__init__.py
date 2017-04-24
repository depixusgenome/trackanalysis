#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere
"""
from  tornado.web   import StaticFileHandler
from  .modal        import DpxModal

dialog = DpxModal.run # pylint: disable=invalid-name

def server(kwa):
    "adds a router to the server"
    router = ("/modaldialog/(.*)", StaticFileHandler, { "path" : "static" })
    kwa['extra_patterns'] = [router]

def document(doc):
    "adds a root to the document"
    doc.add_root(DpxModal())
