#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''Runs the rampapp using flexx framwork'''
import os
import click
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.settings import settings
from bokeh.application.handlers import FunctionHandler
from flexx.webruntime import launch as _flexxlaunch
from flexx.webruntime.common import StreamReader
print("in runrampapp",os.getcwd())
from ramp.rampapp import MyDisplay

def _serverkwargs(kwa):
    server_kwargs = dict(kwa)
    server_kwargs['sign_sessions'] = settings.sign_sessions()
    server_kwargs['secret_key'] = settings.secret_key_bytes()
    server_kwargs['generate_session_ids'] = True
    server_kwargs['use_index'] = True
    server_kwargs['redirect_root'] = True
    return server_kwargs

@click.command()
@click.argument('view')
@click.option("--app", default = 'withtoolbar',
              help = u'Which app mixin to use')
@click.option("--web", 'desktop', flag_value = False,
              help = u'Serve to webbrowser rather than desktop app')
@click.option("--desk", 'desktop', flag_value = True, default = True,
              help = u'Launch as desktop app')
@click.option("--show", flag_value = True, default = False,
              help = u'If using webbrowser, launch it automatically')

def run(view, app, desktop, show): # pylint: disable=unused-argument
    u"Launches an view"
    start = MyDisplay.open
    spec_server = {"title" : "Ramp analysis",
                   "size" : (1000,1000)}
    server = Server(Application(FunctionHandler(start)), **spec_server)

    old = StreamReader.run
    def reader_run(self):
        u''' define StreamReader run function
        '''
        old(self)
        server.stop()

    StreamReader.run = reader_run

    rtime = _flexxlaunch("http://localhost:5006/", **spec_server) # pylint: disable=unused-variable

    server.start()



if __name__ == '__main__':
    run()   # pylint: disable=no-value-for-parameter
