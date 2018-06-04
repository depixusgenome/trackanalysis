#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Different file dialogs."
import sys
from pathlib            import Path
from typing             import List, Optional, Callable, Dict, Tuple
from tkinter            import Tk as _Tk
from tkinter.filedialog import (askopenfilename   as _tkopen,
                                asksaveasfilename as _tksave)
from utils              import initdefaults

_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name
class FileDialogTheme:
    "file dialog info"
    name  = "filedialog"
    types = {'all':      ('all files',               '.*'),
             'trk':      ('track files',             '.trk'),
             'gr':       ('graphics files',          '.gr'),
             'ana':      ('analysis files',          '.ana'),
             'fasta':    ('fasta files',             '.fasta'),
             'xlsx':     ('excel files',             '.xlsx'),
             'csv':      ('comma-separated values',  '.csv')}
    types['any'] = types['all']
    types['*']   = types['all']
    storage: Dict[str, str] = {}
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class BaseFileDialog:
    """
    Deals with filepaths to be opened or saved

    *defaultextension* is first item in *filetypes* by default.

    *filtypes* is a string with format: "description 1: extension | ...".
    Default descriptions and extensions exist for usual file types. One can
    have thus:  *filetypes* = 'trk|*' for track files + any other extension.
    """
    _KFT  = 'filetypes'
    _KEXT = 'defaultextension'
    def __init__(self, **kwa):
        self.defaultextension: Optional[str]  = kwa.get('defaultextension',None)
        self.filetypes       : Optional[str]  = kwa.get('filetypes',       None)
        self.initialdir      : Optional[str]  = kwa.get('initialdir',      None)
        self.initialfile     : Optional[str]  = kwa.get('initialfile',     None)
        self.multiple        : Optional[bool] = kwa.get('multiple',        None)
        self.title           : Optional[str]  = kwa.get('title',           None)
        self._config  = FileDialogTheme()

    @staticmethod
    def exists(path):
        "safe call to Path.exists"
        try:
            return path.exists()
        except OSError:
            return False

    @classmethod
    def firstexistingpath(cls, pot: List[Path]) -> Optional[str]:
        "selects the first existing path from a list"
        exists = cls.exists
        return next((str(i) for i in pot if exists(i)),
                    next((str(i.parent) for i in pot if exists(i.parent)), # type: ignore
                         None))

    @classmethod
    def firstexistingparent(cls, pot: List[Path]) -> Optional[str]:
        "selects the first existing path from a list"
        exists = cls.exists
        return next((str(i) for i in pot if exists(i.parent)), None) # type: ignore

    def _parse_filetypes(self, info:dict):
        if self.filetypes is None:
            return

        def _transf(item):
            ele = tuple(ite.strip() for ite in item.split(':'))
            return self._config.types[ele[0].lower()] if len(ele) == 1 else ele

        info[self._KFT] = [_transf(ite) for ite in self.filetypes.split('|')]

    def _parse_extension(self, info:dict):
        if self.defaultextension is None:
            if self.filetypes is None:
                raise KeyError('Missing defaultextension or filetypes')
            info[self._KEXT] = info[self._KFT][0][1]
        elif not self.defaultextension.startswith('.'):
            info[self._KEXT] = self._config.types[self.defaultextension.strip().lower()][1]

    def _parse_all(self, _):
        info = {key: getattr(self, key)
                for key in self.__dict__
                if getattr(self, key) is not None and key[0] != '_'}
        info.pop('defaults', None)
        info.pop('config',   None)
        info.pop('access',   None)

        self._parse_filetypes(info)
        self._parse_extension(info)
        return info

    def _tk_run(self, info:dict, dialog:Callable):
        root = _Tk()
        root.withdraw()
        root.wm_attributes("-topmost",1)

        rets = dialog(**info,parent=root)
        if rets is None or len(rets) == 0:
            return None
        if (not sys.platform.startswith('win')
                and isinstance(rets, tuple)
                and len(rets) > 1
                and 'initialfile' in info
                and info.get('multiple', False)):
            rets = rets[1:] # discard initial file

        ret = Path(rets if isinstance(rets, str) else next(iter(rets)))
        self.initialdir  = str(ret.parent)
        self.initialfile = str(ret.name)
        return rets

    def open(self):
        "Returns a filepath to be opened."
        return self._tk_run(self._parse_all(True), _tkopen)

    def save(self):
        "Returns a filepath where to save to."
        info = self._parse_all(False)
        info.pop('multiple', None)
        return self._tk_run(info, _tksave)

class FileDialog(BaseFileDialog):
    """
    Deals with filepaths to be opened or saved

    *defaultextension* is first item in *filetypes* by default.

    *filtypes* is a string with format: "description 1: extension | ...".
    Default descriptions and extensions exist for usual file types. One can
    have thus:  *filetypes* = 'trk|*' for track files + any other extension.
    """
    access : Tuple[Callable, Callable]
    def __init__(self, ctrl, storage = None, **kwa):
        super().__init__(**kwa)
        self._config = ctrl.theme.add(self._config, False)
        self.access  = self._getconfig(ctrl, storage), self._setconfig(ctrl, storage)

    @staticmethod
    def storedpaths(ctrl, name, exts) -> List[Path]:
        "returns a stored path"
        fcn = lambda i: ctrl.theme.get("filedialog", "storage", {}).get(i, None)
        pot = [fcn(i.replace('.', '')) for _, i in exts]
        if name is not None:
            pot.insert(0, fcn(name))

        pot = [i for i in pot if i is not None]
        return [Path(i) for i in pot]

    @classmethod
    def _getconfig(cls, ctrl, storage = None):
        def _get(ext, bopen):
            if bopen:
                return cls.firstexistingpath(cls.storedpaths(ctrl, storage, ext))
            return cls.firstexistingparent(cls.storedpaths(ctrl, storage, ext))
        return _get

    @classmethod
    def _setconfig(cls, ctrl, storage = None):
        get    = lambda i: ctrl.theme.get("filedialog", "storage", {}).get(i, None)
        exists = cls.exists
        def _defaultpath(rets, bcheck: bool = True):
            if rets is None:
                return
            vals: Dict[str, str] = {}
            itr   = (rets,) if isinstance(rets, str) else rets
            first = None
            for ret in itr:
                ret = Path(ret)
                if bcheck:
                    if not exists(ret):
                        continue
                    ret = ret.resolve()

                if ret.suffix and get(ret.suffix[1:]) is not None:
                    vals.setdefault(ret.suffix[1:], str(ret))
                if first is None:
                    first = ret
            if storage is not None:
                vals[storage] = str(first)
            ctrl.theme.update("filedialog", storage = vals)

        return _defaultpath

    def _parse_path(self, info:dict, bopen):
        if self.access is None:
            return

        path = self.access[0](info[self._KFT], bopen)
        if path is not None:
            apath = Path(path)
            if apath.is_dir():
                info['initialdir']  = path
            else:
                info['initialdir']  = str(apath.parent)
                info['initialfile'] = str(apath.name)

    def _parse_all(self, bopen):
        info = super()._parse_all(bopen)
        self._parse_path(info, bopen)
        return info

    def _tk_run(self, info:dict, dialog:Callable):
        rets = super()._tk_run(info, dialog)
        if self.access is not None and self.access[1] is not None:
            self.access[1](rets, dialog is _tkopen)
        return rets
