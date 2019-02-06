#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Runs an app"
from   time    import time
from   pathlib import Path
import sys
import glob

def _add_sys_paths():
    paths = (str(Path(__file__).parent.parent.resolve()),)+tuple(glob.glob("*.pyz"))
    for path in paths:
        if path not in sys.path:
            sys.path.append(path)
_add_sys_paths()
# pylint: disable=wrong-import-position
from app.cmdline     import defaultclick, defaultmain, click, WARNINGS, INITIAL_ORDERS
from utils.logconfig import getLogger
LOGS = getLogger()

def _filtr(app, viewcls):
    if 'app.' not in app:
        app += 'app.'+app

    if 'toolbar' in viewcls.__name__.lower() or 'toolbar' in viewcls.__module__:
        app = 'app.default'

    if (('daq' in viewcls.__name__.lower() or 'daq' in viewcls.__module__)
            and 'daq' not in app):
        app = 'daq.'+app
    return app

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
         gui, config, wall, port, raiseerr, nothreading):
    "Launches an view"
    if wall:
        WARNINGS.set(True)
    _files(tracks, files, bead)
    return defaultmain(_filtr, config, view, gui, port, raiseerr, nothreading,
                       "taskapp.toolbar")

if __name__ == '__main__':
    main()   # pylint: disable=no-value-for-parameter
