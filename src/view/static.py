#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all static view aspects here"
from  tornado.web   import StaticFileHandler

ROUTE = 'view'

def server(kwa):
    "adds a router to the server"
    router = ("/%s/(.*)" % ROUTE, StaticFileHandler, { "path" : "static" })
    kwa.setdefault('extra_patterns', []).append(router)
