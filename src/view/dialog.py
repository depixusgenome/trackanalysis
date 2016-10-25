#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Different file dialogs."

from typing             import Callable, Tuple, cast # pylint: disable=unused-import
from tkinter            import Tk as _Tk
from tkinter.filedialog import (askopenfilename   as _tkopen,
                                asksaveasfilename as _tksave)

DEFAULTS = {'all': (u'all files',               '.*'),
            'trk': (u'track files',             '.trk'),
            'ana': (u'analysis files',          '.ana'),
            'xls': (u'excel files',             '.xlsx'),
            'csv': (u'comma-separated files',   '.csv')}
DEFAULTS['any'] = DEFAULTS['all']
DEFAULTS['*']   = DEFAULTS['all']

_KFTYPE = 'filetypes'
_KEXT = 'defaultextension'

def _parse_filetypes(info:dict):
    if _KFTYPE not in info:
        return

    def _transf(item):
        ele = tuple(ite.strip() for ite in item.split(u':'))
        return DEFAULTS[ele[0].lower()] if len(ele) == 1 else ele

    info[_KFTYPE] = [_transf(ite) for ite in info[_KFTYPE].split(u'|')]

def _parse_extension(info:dict):
    if _KEXT not in info:
        if _KFTYPE not in info:
            raise KeyError('Missing defaultextension or filetypes')
        info[_KEXT] = info[_KFTYPE][0][1]
    elif not info[_KEXT].startswith('.'):
        info[_KEXT] = DEFAULTS[info[_KEXT].strip().lower()][1]

def _tk_run(locs:dict, dialog:'Callable'):
    info = {name: val for name, val in locs.items() if val is not None}
    _parse_filetypes(info)
    _parse_extension(info)

    _Tk().withdraw()
    ret = dialog(**info)
    return None if ret is None or len(ret) == 0 else ret

# pylint: disable=unused-argument,too-many-arguments
def openfile(defaultextension = None,
             filetypes        = None,
             initialdir       = None,
             initialfile      = None,
             multiple         = None,
             title            = None,
            ):
    u"""
    returns a filepath to be opened.

    *defaultextension* is first item in *filetypes* by default.

    *filtypes* is a string with format: "description 1: extension | ...".
    Default descriptions and extensions exist for usual file types. One can
    have thus:  *filetypes* = 'trk|*' for track files + any other extension.
    """
    return _tk_run(locals(), _tkopen)

def savefile(defaultextension = None,
             filetypes        = None,
             initialdir       = None,
             initialfile      = None,
             title            = None,
            ):
    u"""
    returns a filepath to be saved.

    *defaultextension* is first item in *filetypes* by default.

    *filtypes* is a string with format: "description 1: extension | ...".
    Default descriptions and extensions exist for usual file types. One can
    have thus:  *filetypes* = 'trk|*' for track files + any other extension.
    """
    return _tk_run(locals(), _tksave)
