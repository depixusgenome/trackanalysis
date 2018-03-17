#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Runs an app"
from app.cmdline import defaultclick, defaultmain

@defaultclick()
def main(view, gui, port, raiseerr, singlethread):
    "Launches an view"
    defaultmain(view, gui, port, raiseerr, singlethread, "daq.app.default")

if __name__ == '__main__':
    main()   # pylint: disable=no-value-for-parameter
