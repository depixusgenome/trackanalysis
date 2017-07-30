#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all static view aspects here"
import sys
from   tornado     import gen
from   tornado.web import StaticFileHandler, RequestHandler

ROUTE = 'view'
if 'app.scripting' in sys.modules:
    sys.modules['app.scripting'].addload(__name__)

def server(kwa):
    "adds a router to the server"
    router = ("/%s/(.*)" % ROUTE, StaticFileHandler, { "path" : "static" })
    kwa.setdefault('extra_patterns', []).append(router)

class StaticHandler(RequestHandler):    # pylint: disable=abstract-method
    'Implements a custom Tornado handler for autoloading css'
    def initialize(self, *args, **kw):  # pylint: disable=arguments-differ
        pass

    @gen.coroutine
    def get(self, *args, **kwargs):
        self.set_header("Content-Type", 'text/css')
        self.write(".dpx-peaksplot-widget { width: 520px;}\n"
                   ".dpx-peaksplot-canvas { width: auto;}\n")
