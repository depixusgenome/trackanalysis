#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Runs an app"
from app.cmdline   import defaultclick, defaultmain, click
from app.scripting import orders

@defaultclick()
@click.option("-s", "--servertype",
              type       = click.Choice(['sim', 'admin', 'none']),
              default    = 'admin',
              help       = 'The server type to use.')
@click.option("--rtsp",
              default    = "",
              help       = 'set the rtsp adress')
def main(view, gui, port, raiseerr, nothreading,  # pylint: disable=too-many-arguments
         servertype, rtsp):
    "Launches an view"
    from  daq.app.default import VIEWS
    if servertype == 'sim':
        VIEWS.insert(0, "daq.server.simulator.DAQFoVServerSimulatorView")
        VIEWS.insert(0, "daq.server.simulator.DAQBeadsServerSimulatorView")
    elif servertype == 'admin':
        VIEWS.append("daq.server.adminview.DAQAdminView")

    if rtsp and '//' not in rtsp:
        rtsp = "rtsp://"+rtsp

    def _config(ctrl):
        if rtsp:
            ctrl.daq.config.network.camera.address = rtsp

    orders().default_config = _config
    defaultmain(view, gui, port, raiseerr, nothreading, "daq.app.toolbar")

if __name__ == '__main__':
    main()   # pylint: disable=no-value-for-parameter
