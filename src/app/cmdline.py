#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Runs an app"
from   pathlib import Path
from   time    import time
import logging
import sys
import glob
import subprocess
import random
import inspect

import click

def _add_sys_paths():
    paths = (str(Path(__file__).parent.parent.resolve()),)+tuple(glob.glob("*.pyz"))
    for path in paths:
        if path not in sys.path:
            sys.path.append(path)
_add_sys_paths()


# pylint: disable=wrong-import-position
import utils.warningsconfig   #  pylint: disable=unused-import
from utils.logconfig    import getLogger
from bokeh.resources    import DEFAULT_SERVER_PORT # pylint: disable=wrong-import-order
from app.scripting      import INITIAL_ORDERS
LOGS = getLogger()

def _without_cls(vname, cname):
    viewmod = __import__(vname)
    for name in vname.split('.')[1:]:
        viewmod = getattr(viewmod, name)

    pred = lambda i: (isinstance(i, type)
                      and (i.__module__ == viewmod.__name__
                           or i.__module__.startswith(viewmod.__name__+'.'))
                      and i.__name__.lower() == cname)
    pot  = tuple(i for _, i in inspect.getmembers(viewmod, pred))
    if len(pot) == 0:
        return _without_cls(vname+".view", cname)
    assert len(pot) == 1
    return pot[0]

def _from_path(view):
    pview = Path(view)
    if pview.exists():
        name = (pview.parent.stem+'view' if pview.stem == 'view'        else
                pview.stem               if pview.stem.endswith('view') else
                pview.stem+'view')

        mod = str(pview.parent/pview.stem).replace('/', '.').replace('\\', '.')
        return _without_cls(mod, name)
    return None

def _from_module(view):
    if '/' in view or '\\' in view:
        view = view.replace('/', '.').replace('\\', '.')
        if view.endswith('.py'):
            view = view[:-3]

    if view.startswith('view.'):
        view = view[5:]

    if '.' not in view:
        view = view.lower()+'.'+view
    try:
        ind  = view.rfind('.')
        name = view[ind+1:]+'view'
        if name == 'viewview':
            name = view[:ind][view[:ind].rfind('.')+1:]+'view'
        val = _without_cls(view, name)
        if val is not None:
            return val
    except: # pylint: disable=bare-except
        pass

    try:
        viewmod  = __import__(view[:view.rfind('.')],
                              fromlist = view[view.rfind('.')+1:])
    except ImportError:
        viewmod  = __import__('view.'+view[:view.rfind('.')],
                              fromlist = view[view.rfind('.')+1:])
    return getattr(viewmod, view[view.rfind('.')+1:])

def _win_opts():
    if sys.platform.startswith("win"):
        # Get rid of console windows
        import bokeh.util.compiler as compiler # pylint: disable=useless-import-alias
        # First find the nodejs path. This must be done with shell == False
        compiler._nodejs_path() # pylint: disable=protected-access
        # Now set shell == True to get rid of consoles
        def _Popen(*args, **kwargs):
            kwargs['shell'] = True
            return subprocess.Popen(*args, **kwargs)
        compiler.Popen = _Popen

def _debug(raiseerr, nothreading):
    if nothreading:
        import view.base as _base
        _base.SINGLE_THREAD = True

    if raiseerr:
        from app.maincontrol import DisplayController
        DisplayController.CATCHERROR = False

def _files(directory, files, bead):
    def _started(_, start = time()):
        LOGS.info("done loading in %d seconds", time()-start)
    INITIAL_ORDERS.append(_started)

    if len(directory):
        def _opentracks(ctrl):
            ctrl.tasks.opentrack(dict(zip(('tracks', 'grs', 'match'),
                                          (i if i else None for i in directory))))
        INITIAL_ORDERS.append(_opentracks)

    if len(files):
        def _open(ctrl):
            if "filedialog" in ctrl.theme:
                storage = dict(ctrl.theme.get("filedialog", "storage", {}))
                storage['open'] = files[0]
                ctrl.theme.update("filedialog", storage = storage)
            ctrl.tasks.opentrack(files)
        INITIAL_ORDERS.append(_open)

    if (len(files) or len(directory)) and  bead is not None:
        def _setbead(ctrl):
            ctrl.display.update("tasks", bead = bead)
        INITIAL_ORDERS.append(_setbead)

def _launch(view, app, gui, kwa):
    viewcls = _from_path(view)
    if viewcls is None:
        viewcls = _from_module(view)

    if 'app.' not in app:
        app += 'app.'+app

    if 'toolbar' in viewcls.__name__.lower() or 'toolbar' in viewcls.__module__:
        app = 'app.default'

    if (('daq' in viewcls.__name__.lower() or 'daq' in viewcls.__module__)
            and 'daq' not in app):
        app = 'daq.'+app

    kwa['runtime'] = gui
    lfcn           = 'launch' if gui.endswith('app') else 'serve'
    if '.' in app and 'A' <= app[app.rfind('.')+1] <= 'Z':
        mod  = app[:app.rfind('.')]
        attr = app[app.rfind('.')+1:]
        launchmod = getattr(__import__(mod, fromlist = [attr]), attr)
    else:
        launchmod = __import__(app, fromlist = [lfcn])

    return getattr(launchmod, lfcn)(viewcls, **kwa)

def _port(port):
    return int(random.randint(5000, 8000)) if port == 'random' else int(port)

def _version(ctx, _, value):
    import version
    if not value or ctx.resilient_parsing:
        return
    click.echo('TrackAnalysis  ' + version.version())
    click.echo(' - git hash:   ' + version.lasthash())
    click.echo(' - created on: ' + version.hashdate())
    click.echo(' - compiler:   ' + version.compiler())
    ctx.exit()

# pylint: disable=too-many-arguments
def defaultmain(view, gui, port, raiseerr, nothreading, defaultapp):
    "Launches an view"
    _debug(raiseerr, nothreading)
    _win_opts()

    kwargs = dict(port = _port(port), apponly = False)
    server = _launch(view, defaultapp, gui, kwargs)

    if gui == 'default':
        gui = 'browser'
    if gui.endswith('browser'):
        server.io_loop.add_callback(lambda: server.show("/"))

    log = lambda: LOGS.info(' http://%(address)s:%(port)s',
                            {'port': kwargs['port'], 'address': 'localhost'})
    server.io_loop.add_callback(log)
    server.run_until_shutdown()
    logging.shutdown()

def defaultclick(*others):
    """
    sets default command line options
    """
    def _wrapper(fcn):
        fcn = click.option("--nothreading",
                           flag_value = True,
                           default    = False,
                           help       = '[DEBUG] Runs plots in single thread')(fcn)
        fcn = click.option("--raiseerr",
                           flag_value = True,
                           default    = False,
                           help       = '[DEBUG] Whether errors should be caught')(fcn)
        fcn = click.option('-p', "--port",
                           default    = str(DEFAULT_SERVER_PORT),
                           help       = 'Port used: use "random" for any')(fcn)
        fcn = click.option("-g", "--gui",
                           type       = click.Choice(['app', 'browser', 'default',
                                                      'firefox-browser', 'chrome-browser',
                                                      'firefox-app', 'chrome-app',
                                                      'none']),
                           default    = 'app',
                           help       = 'The type of browser to use.')(fcn)

        for i in others:
            fcn = i(fcn)

        fcn = click.argument('view')(fcn)
        fcn = click.option('--version', is_flag = True, callback = _version,
                           expose_value = False, is_eager = True)(fcn)

        return click.command()(fcn)
    return _wrapper

@defaultclick(click.option('-b', "--bead",
                           type       = int,
                           default    = None,
                           help       = 'Opens to this bead'),
              click.option("--tracks",
                           type       = str,
                           nargs      = 3,
                           help       = 'track path, gr path and match'),
              click.argument('files', nargs = -1, type = click.Path()))
def main(view, files, tracks, bead,  # pylint: disable=too-many-arguments
         gui, port, raiseerr, nothreading):
    "Launches an view"
    _files(tracks, files, bead)
    return defaultmain(view, gui, port, raiseerr, nothreading, "app.toolbar")

if __name__ == '__main__':
    main()   # pylint: disable=no-value-for-parameter
