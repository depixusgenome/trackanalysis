#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Runs an app"
import sys
from   pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
# pylint: disable=wrong-import-position
from app.cmdline import defaultclick, defaultmain, defaultinit, click, INITIAL_ORDERS

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

DEFAULT_VIEW = "hybridstat.view.HybridStatView"

@defaultclick("TrackAnalysis", defaultview = DEFAULT_VIEW)
@click.option('-b', "--bead",
              type       = int,
              default    = None,
              help       = 'Opens to this bead')
@click.option("--tracks",
              type       = str,
              nargs      = 3,
              help       = 'track path, gr path and match')
@click.argument('files', nargs = -1, type = click.Path())
def main(view, files, tracks, bead,  # pylint: disable=too-many-arguments
         gui, config, wall, port, raiseerr, nothreading):
    "Launches an view"
    if any(view.endswith(i) for i in (".trk", ".ana", ".xlsx", ".pk")) or "/" in view:
        files = (view,)+files
        view  = DEFAULT_VIEW

    defaultinit(config, wall, raiseerr, nothreading)
    _files(tracks, files, bead)
    return defaultmain(_filtr, view, gui, port, "taskapp.toolbar")

if __name__ == '__main__':
    main()   # pylint: disable=no-value-for-parameter
