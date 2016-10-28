#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Different file dialogs."

from typing             import Callable
from tkinter            import Tk as _Tk
from tkinter.filedialog import (askopenfilename   as _tkopen,
                                asksaveasfilename as _tksave)
class FileDialog:
    u"""
    Deals with filepaths to be opened or saved

    *defaultextension* is first item in *filetypes* by default.

    *filtypes* is a string with format: "description 1: extension | ...".
    Default descriptions and extensions exist for usual file types. One can
    have thus:  *filetypes* = 'trk|*' for track files + any other extension.
    """
    DEFAULTS = {'all': (u'all files',               '.*'),
                'trk': (u'track files',             '.trk'),
                'ana': (u'analysis files',          '.ana'),
                'xls': (u'excel files',             '.xlsx'),
                'csv': (u'comma-separated files',   '.csv')}
    DEFAULTS['any'] = DEFAULTS['all']
    DEFAULTS['*']   = DEFAULTS['all']

    _KFT  = 'filetypes'
    _KEXT = 'defaultextension'
    def __init__(self, **kwa):
        self.defaultextension = kwa.get('defaultextension',None)  # type: Optional[str]
        self.filetypes        = kwa.get('filetypes',       None)  # type: Optional[str]
        self.initialdir       = kwa.get('initialdir',      None)  # type: Optional[str]
        self.initialfile      = kwa.get('initialfile',     None)  # type: Optional[str]
        self.multiple         = kwa.get('multiple',        None)  # type: Optional[bool]
        self.title            = kwa.get('title',           None)  # type: Optional[str]

    def _parse_filetypes(self, info:dict):
        if self.filetypes is None:
            return

        def _transf(item):
            ele = tuple(ite.strip() for ite in item.split(u':'))
            return self.DEFAULTS[ele[0].lower()] if len(ele) == 1 else ele

        info[self._KFT] = [_transf(ite) for ite in self.filetypes.split(u'|')]

    def _parse_extension(self, info:dict):
        if self.defaultextension is None:
            if self.filetypes is None:
                raise KeyError('Missing defaultextension or filetypes')
            info[self._KEXT] = info[self._KFT][0][1]
        elif not self.defaultextension.startswith('.'):
            info[self._KEXT] = self.DEFAULTS[self.defaultextension.strip().lower()][1]

    def _tk_run(self, keys, dialog:Callable):
        info = {key: getattr(self, key)
                for key in keys if getattr(self, key) is not None}
        self._parse_filetypes(info)
        self._parse_extension(info)

        _Tk().withdraw()
        ret = dialog(**info)
        if ret is None or len(ret) == 0:
            return None

        self.initialdir  = ret[:ret.rfind('/')]
        self.initialfile = ret[len(self.initialdir):]
        return ret

    def open(self):
        u"Returns a filepath to be opened."
        return self._tk_run(self.__dict__.keys(), _tkopen)

    def save(self):
        u"Returns a filepath where to save to."
        return self._tk_run(set(self.__dict__.keys()) - {'multiple'}, _tksave)
