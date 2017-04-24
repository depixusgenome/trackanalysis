#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Sets-up the logging"
import logging
import os
import sys
try:
    # setup using bokeh if available
    import bokeh # pylint: disable=unused-import
except ImportError:
    pass
else:
    import bokeh.util.logconfig # pylint: disable=unused-import

PREFIX = 'DEPIXUS_'
LOGGER = 'trackanalysis'

def getLogger(arg = None):
    "the root logger"
    if arg is None:
        return logging.getLogger(LOGGER)
    else:
        return logging.getLogger(LOGGER+'.'+arg)

def getEnvironLevel():
    "sets the level"
    var    = os.environ.get(PREFIX+'LOG_LEVEL', 'info').strip().lower()
    levels = {'debug': logging.DEBUG,
              'info' : logging.INFO,
              'warn' : logging.WARNING,
              'error': logging.ERROR,
              'fatal': logging.CRITICAL,
              'none' : None}
    return levels[var]

if not (logging.getLogger().handlers or getLogger().handlers):
    DEFAULT = logging.StreamHandler(sys.stdout)
    DEFAULT.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
    getLogger().addHandler(DEFAULT)
    getLogger().propagate = False
    getLogger().setLevel(getEnvironLevel())
else:
    DEFAULT = None

def basicConfig(*args, **kwargs):
    "A logging.basicConfig() wrapper that also undoes the default configuration."
    global DEFAULT # pylint: disable=global-statement
    if DEFAULT is not None:
        getLogger().removeHandler(DEFAULT)
        getLogger().propagate = True
        DEFAULT = None
    return logging.basicConfig(*args, **kwargs)
