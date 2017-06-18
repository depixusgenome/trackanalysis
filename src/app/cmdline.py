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
import utils.warnings   #  pylint: disable=unused-import
from utils.logconfig    import getLogger
from bokeh.resources    import DEFAULT_SERVER_PORT
from app.scripting      import INITIAL_ORDERS
LOGS = getLogger()

def _without_cls(vname, cname):
    viewmod = __import__(vname)
    for name in vname.split('.')[1:]:
        viewmod = getattr(viewmod, name)

    pred = lambda i: (isinstance(i, type)
                      and i.__module__ == viewmod.__name__
                      and i.__name__.lower() == cname)
    pot  = tuple(i for _, i in inspect.getmembers(viewmod, pred))
    if len(pot) == 0:
        return _without_cls(vname+".view", cname)
    assert len(pot) == 1
    return pot[0]

def _from_path(view):
    pview = Path(view)
    if pview.exists():
        name = pview.stem+'view'
        if name == 'viewview':
            name = pview.parent.stem+'view'

        mod = str(pview.parent/pview.stem).replace('/', '.').replace('\\', '.')
        return _without_cls(mod, name)

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

def _electron(server, **kwa):
    electron = None
    iswin    = sys.platform.startswith('win')
    for electron in (str(Path('node_modules')/'.bin'/'electron'), 'electron'):
        try:
            if subprocess.check_call([electron, '-v'],
                                     shell  = iswin,
                                     stdout = subprocess.DEVNULL,
                                     stderr = subprocess.DEVNULL) == 0:
                break
        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            pass
    else:
        electron = None

    if electron is not None:
        jscode = """
            const {app, BrowserWindow} = require('electron')

            let win

            function createWindow () {
                win = new BrowserWindow({width:1000, height:1000, title: "%s"})

                win.loadURL("http:\\\\localhost:%d")
                win.setMenu(null);

                win.on('closed', () => { win = null })
            }

            app.on('ready', createWindow)

            app.on('window-all-closed', () => { app.quit() })

            app.on('activate', () => { if (win === null) { createWindow() } })
            """ % (server.MainView.APPNAME,
                   kwa.get('port', DEFAULT_SERVER_PORT))

        import tempfile
        path = tempfile.mktemp("_trackanalysis.js")
        with open(path, "w", encoding="utf-8") as stream:
            print(jscode, file = stream)

        subprocess.Popen([electron, path], shell = iswin)
        server.appfunction.stoponnosession = True
    else:
        server.show("/")

def _win_opts():
    if sys.platform.startswith("win"):
        # Get rid of console windows
        import bokeh.util.compiler as compiler
        # First find the nodejs path. This must be done with shell == False
        compiler._nodejs_path() # pylint: disable=protected-access
        # Now set shell == True to get rid of consoles
        def _Popen(*args, **kwargs):
            kwargs['shell'] = True
            return subprocess.Popen(*args, **kwargs)
        compiler.Popen = _Popen

def _debug(raiseerr, singlethread):
    if singlethread:
        import view.base as _base
        _base.SINGLE_THREAD = True

    if raiseerr:
        import app.launcher as app

        def _cnf(ctrl):
            ctrl.getGlobal('config').catcherror.default         = False
            ctrl.getGlobal('config').catcherror.toolbar.default = False
        app.DEFAULT_CONFIG = _cnf

def _files(files, bead):
    def _started(_, start = time()):
        LOGS.info("done loading in %d seconds", time()-start)
    INITIAL_ORDERS.append(_started)

    if len(files):
        def _open(ctrl):
            ctrl.getGlobal('config').last.path.open.set(files[0])
            ctrl.openTrack(files)
            if bead is not None:
                ctrl.getGlobal("project").bead.set(bead)
        INITIAL_ORDERS.append(_open)

def _launch(view, app, desktop, kwa):
    viewcls = _from_path(view)
    if viewcls is None:
        viewcls = _from_module(view)

    if not app.startswith('app.'):
        app += 'app.'+app

    if 'toolbar' in viewcls.__name__.lower():
        app = 'app.Defaults'

    if '.' in app and 'A' <= app[app.rfind('.')+1] <= 'Z':
        mod  = app[:app.rfind('.')]
        attr = app[app.rfind('.')+1:]
        launchmod = getattr(__import__(mod, fromlist = (attr,)), attr)
    else:
        launchmod = __import__(app, fromlist = (('serve', 'launch')[desktop],))

    launch = getattr(launchmod, ('serve', 'launch')[desktop])
    return launch(viewcls, **kwa)

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

@click.command()
@click.option('--version', is_flag = True, callback = _version,
              expose_value = False, is_eager = True)
@click.argument('view')
@click.argument('files', nargs = -1, type = click.Path())
@click.option('-b', "--bead",
              type       = int,
              default    = None,
              help       = 'Opens to this bead')
@click.option("-g", "--gui",
              type       = click.Choice(['firefox', 'chrome', 'default', 'none']),
              default    = 'firefox',
              help       = 'The type of browser to use.')
@click.option('-p', "--port",
              default    = str(DEFAULT_SERVER_PORT),
              help       = 'Port used: use "random" for any')
@click.option("--raiseerr",
              flag_value = True,
              default    = False,
              help       = '[DEBUG] Whether errors should be caught')
@click.option("--singlethread",
              flag_value = True,
              default    = False,
              help       = '[DEBUG] Runs plots in single thread')
def main(view, files, bead,  # pylint: disable=too-many-arguments
         gui, port, raiseerr, singlethread):
    "Launches an view"
    _debug(raiseerr, singlethread)
    _win_opts()

    kwargs = dict(port = _port(port), apponly = False)
    if gui != 'firefox':
        kwargs['unused_session_linger_milliseconds'] = 60000

    _files(files, bead)
    server = _launch(view, 'app.BeadToolbar', gui == 'firefox', kwargs)

    if gui == 'chrome':
        server.io_loop.add_callback(lambda: _electron(server, port = kwargs['port']))
    elif gui == 'default':
        server.io_loop.add_callback(lambda: server.show("/"))

    log = lambda: LOGS.info(' http://%(address)s:%(port)s',
                            {'port': kwargs['port'], 'address': 'localhost'})
    server.io_loop.add_callback(log)
    server.run_until_shutdown()
    logging.shutdown()

if __name__ == '__main__':
    main()   # pylint: disable=no-value-for-parameter
