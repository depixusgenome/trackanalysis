#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Runs an app"
from app.cmdline import defaultclick, defaultmain, click

@defaultclick()
@click.option("--sim",
              flag_value = True,
              default    = False,
              help       = '[DEBUG] adds a server simulator')
def main(view, gui, port, raiseerr, singlethread, sim): # pylint: disable=too-many-arguments
    "Launches an view"
    from  daq.app.default import VIEWS
    if sim:
        VIEWS.insert(0, "daq.server.simulator.DAQFoVServerSimulatorView")
        VIEWS.insert(0, "daq.server.simulator.DAQBeadsServerSimulatorView")
    else:
        VIEWS.append("daq.server.adminview.DAQAdminView")
    defaultmain(view, gui, port, raiseerr, singlethread, "daq.app.toolbar")

if __name__ == '__main__':
    main()   # pylint: disable=no-value-for-parameter
