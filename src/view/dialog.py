#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Different file dialogs."
from pathlib            import Path
from typing             import Callable
from tkinter            import Tk as _Tk
from tkinter.filedialog import (askopenfilename   as _tkopen,
                                asksaveasfilename as _tksave)
class FileDialog:
    """
    Deals with filepaths to be opened or saved

    *defaultextension* is first item in *filetypes* by default.

    *filtypes* is a string with format: "description 1: extension | ...".
    Default descriptions and extensions exist for usual file types. One can
    have thus:  *filetypes* = 'trk|*' for track files + any other extension.
    """
    DEFAULTS = {'all':      (u'all files',               '.*'),
                'trk':      (u'track files',             '.trk'),
                'gr':       (u'graphics files',          '.gr'),
                'ana':      (u'analysis files',          '.ana'),
                'fasta':    (u'fasta files',             '.fasta'),
                'xls':      (u'excel files',             '.xlsx'),
                'csv':      (u'comma-separated files',   '.csv')}
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
        self.config           = None   # type: Tuple[Callable, Callable]

        cnf = kwa.get('config', None)  # type: ignore
        if hasattr(cnf, 'getGlobal'):
            cnf          = cnf.getGlobal('config').last.path
            cnf.defaults = dict.fromkeys(self.DEFAULTS, None)
        if hasattr(cnf, 'get'):
            self.config = self._getconfig(cnf), self._setconfig(cnf)
        else:
            self.config = cnf

    @staticmethod
    def _getconfig(cnf):
        def _defaultpath(ext):
            ext = ext.replace('.', '')
            return cnf.get(ext, default = None)
        return _defaultpath

    @staticmethod
    def _setconfig(cnf):
        def _defaultpath(rets):
            vals = {}
            itr  = (rets,) if isinstance(rets, str) else rets
            for ret in itr:
                ret = Path(ret).resolve()
                vals.setdefault(ret.suffix[1:], str(ret))
            cnf.update(**vals)

        return _defaultpath

    def _parse_filetypes(self, info:dict):
        if self.filetypes is None:
            return

        def _transf(item):
            ele = tuple(ite.strip() for ite in item.split(':'))
            return self.DEFAULTS[ele[0].lower()] if len(ele) == 1 else ele

        info[self._KFT] = [_transf(ite) for ite in self.filetypes.split('|')]

    def _parse_extension(self, info:dict):
        if self.defaultextension is None:
            if self.filetypes is None:
                raise KeyError('Missing defaultextension or filetypes')
            info[self._KEXT] = info[self._KFT][0][1]
        elif not self.defaultextension.startswith('.'):
            info[self._KEXT] = self.DEFAULTS[self.defaultextension.strip().lower()][1]

    def _parse_path(self, info:dict):
        if self.config is None:
            return

        path = None
        for _, ext in info[self._KFT]:
            path = self.config[0](ext)
            if path is None:
                continue

            info['initialdir']  = str(Path(path).parent)
            info['initialfile'] = str(Path(path).name)
            break

    def _parse_all(self):
        info = {key: getattr(self, key)
                for key in self.__dict__ if getattr(self, key) is not None}
        info.pop('config', None)

        self._parse_filetypes(info)
        self._parse_extension(info)
        self._parse_path(info)
        return info

    def _tk_run(self, info:dict, dialog:Callable):
        root = _Tk()
        root.withdraw()
        root.wm_attributes("-topmost",1)

        rets = dialog(**info,parent=root)
        if rets is None or len(rets) == 0:
            return None
        if isinstance(rets, tuple) and 'initialfile' in info and info.get('multiple', False):
            rets = rets[1:] # discard initiali file

        ret = Path(rets if isinstance(rets, str) else next(iter(rets)))
        self.initialdir  = ret.parent
        self.initialfile = ret.name

        if self.config is not None:
            self.config[1](rets)
        return rets

    def open(self):
        "Returns a filepath to be opened."
        return self._tk_run(self._parse_all(), _tkopen)

    def save(self):
        "Returns a filepath where to save to."
        info = self._parse_all()
        info.pop('multiple', None)
        return self._tk_run(info, _tksave)
