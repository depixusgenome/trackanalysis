#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Sets-up the logging"
from   pathlib  import Path
import logging
import logging.config
import os
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

def logToFile(path):
    "adds a log to file"
    assert not any(hdl.get_name() == 'file' for hdl in getLogger().handlers)
    if path is None:
        return

    if not Path(path).parent.exists(): # pylint: disable=no-member
        # pylint: disable=no-member,bare-except
        try:
            Path(path).parent.mkdir(parents = True, exist_ok = True)
        except:
            getLogger().exception('Could not log to file')
            return

    hdl = logging.handlers.RotatingFileHandler(path,
                                               maxBytes    = 1024,
                                               backupCount = 3,
                                               encoding    = 'utf-8')
    hdl.set_name('file')
    hdl.setLevel(getEnvironLevel())
    fmt  = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date = '%m/%d/%Y %I:%M:%S %p'
    hdl.setFormatter(logging.Formatter(fmt, date))
    getLogger().addHandler(hdl)

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
    def _setdefault():
        lvl = getEnvironLevel()
        cnf = {'version'   : 1,
               'formatters': {'brief'  : {'format'   : logging.BASIC_FORMAT}},
               'handlers'  : {'console': {'class'    : 'logging.StreamHandler',
                                          'formatter': 'brief',
                                          'level'    : lvl,
                                          'stream'   : 'ext://sys.stdout'}},
               'loggers'   : {LOGGER   : {'level'    : lvl,
                                          'propagate': False,
                                          'handlers' : ['console']}}}
        logging.config.dictConfig(cnf)

    _setdefault()

def basicConfig(*args, **kwargs):
    "A logging.basicConfig() wrapper that also undoes the default configuration."
    for hdl in tuple(getLogger().handlers):
        getLogger().removeHandler(hdl)
    getLogger().propagate = True
    return logging.basicConfig(*args, **kwargs)
