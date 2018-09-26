#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''Runs the rampapp using webruntime framework'''
import click
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.settings import settings
from bokeh.application.handlers import FunctionHandler

def _serverkwargs(kwa):
    server_kwargs = dict(kwa)
    server_kwargs['sign_sessions'] = settings.sign_sessions()
    server_kwargs['secret_key'] = settings.secret_key_bytes()
    server_kwargs['generate_session_ids'] = True
    server_kwargs['use_index'] = True
    server_kwargs['redirect_root'] = True
    return server_kwargs

@click.command()
@click.option("--width", 'width', default = 800,
              help = 'Sets width of the window')
@click.option("--height", 'height', default = 800,
              help = 'Sets height of the window')

def run(width,height): # pylint: disable=unused-argument
    "Launches an view"
    from . import rampapp
    viewcls = rampapp.MyDisplay
    #spec_server=_serverkwargs({"title":"Ramp analysis",
    #                           "size":(width,height)})

    spec_server=_serverkwargs({"title":"Ramp analysis"})
    #                           "size":(width,height)})
    start = viewcls.open
    server = Server(Application(FunctionHandler(start)), **spec_server)

    from webruntime._common import StreamReader
    from webruntime         import launch as _flexxlaunch

    old = StreamReader.run
    def reader_run(self):
        ''' define StreamReader run function
        '''
        old(self)
        server.stop()

    StreamReader.run = reader_run

    rtime = _flexxlaunch("http://localhost:5006/", **spec_server) # pylint: disable=unused-variable
    server.start()



if __name__ == '__main__':
    run()   # pylint: disable=no-value-for-parameter
