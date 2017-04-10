#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Runs an app"
from   pathlib import Path
import random
import inspect
import click

def _from_path(view):
    pview = Path(view)
    if not pview.exists():
        return
    vname   = str(pview.parent/pview.stem).replace('/', '.').replace('\\', '.')
    viewmod = __import__(vname)
    for name in vname.split('.')[1:]:
        viewmod = getattr(viewmod, name)

    name = pview.stem+'view'
    pred = lambda i: (isinstance(i, type)
                      and i.__module__ == viewmod.__name__
                      and i.__name__.lower() == name)
    pot  = tuple(i for _, i in inspect.getmembers(viewmod, pred))
    assert len(pot) == 1
    return pot[0]

def _from_module(view):
    if view.startswith('view.'):
        view = view[5:]

    if '.' not in view:
        view = view.lower()+'.'+view
    try:
        viewmod  = __import__(view[:view.rfind('.')],
                              fromlist = view[view.rfind('.')+1:])
    except ImportError:
        viewmod  = __import__('view.'+view[:view.rfind('.')],
                              fromlist = view[view.rfind('.')+1:])
    return getattr(viewmod, view[view.rfind('.')+1:])

@click.command()
@click.argument('view')
@click.option("--app", default = 'app.BeadToolBar',
              help = u'Which app mixin to use')
@click.option("--web", 'desktop', flag_value = False,
              help = u'Serve to webbrowser rather than desktop app')
@click.option("--desk", 'desktop', flag_value = True, default = True,
              help = u'Launch as desktop app')
@click.option("--show", flag_value = True, default = False,
              help = u'If using webbrowser, launch it automatically')
@click.option("--port", default = '5006',
              help = u'port used: use "random" for any')
@click.option('-r', "--raiseerr", flag_value = True, default = False,
              help = u'Wether errors should be caught')
def run(view, app, desktop, show, port, raiseerr): # pylint: disable=too-many-arguments
    u"Launches an view"
    viewcls = _from_path(view)
    if viewcls is None:
        viewcls = _from_module(view)

    if not app.startswith('app.'):
        app += 'app.'+app

    if view.startswith('toolbar'):
        app = 'app.Defaults'

    if '.' in app and 'A' <= app[app.rfind('.')+1] <= 'Z':
        mod  = app[:app.rfind('.')]
        attr = app[app.rfind('.')+1:]
        launchmod = getattr(__import__(mod, fromlist = (attr,)), attr)
    else:
        launchmod = __import__(app, fromlist = (('serve', 'launch')[desktop],))

    launch = getattr(launchmod, ('serve', 'launch')[desktop])
    if port == 'random':
        port = random.randint(5000, 8000)
    else:
        port = int(port)

    if raiseerr:
        import app

        def _cnf(ctrl):
            ctrl.getGlobal('config').catcherror.default         = False
            ctrl.getGlobal('config').catcherror.toolbar.default = False
        app.DEFAULT_CONFIG = _cnf

    server = launch(viewcls, port = port)
    if (not desktop) and show:
        server.io_loop.add_callback(lambda: server.show('/'))
    server.start()
    server.io_loop.start()

if __name__ == '__main__':
    run()   # pylint: disable=no-value-for-parameter
