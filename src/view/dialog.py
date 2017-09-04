#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Different file dialogs."
import sys
from pathlib            import Path
from typing             import List, Optional, Callable, Dict # pylint: disable=unused-import
from tkinter            import Tk as _Tk
from tkinter.filedialog import (askopenfilename   as _tkopen,
                                asksaveasfilename as _tksave)
_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name
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
                'xlsx':     (u'excel files',             '.xlsx'),
                'csv':      (u'comma-separated values',  '.csv')}
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

        ctrl = kwa.get('config', None)  # type: ignore
        if hasattr(ctrl, 'getGlobal'):
            self.globals(ctrl).defaults = dict.fromkeys(self.DEFAULTS, None)

        if isinstance(ctrl, (tuple, list)):
            self.config = ctrl
        else:
            storage = kwa.get('storage', None)
            if storage is not None:
                self.globals(ctrl)[storage].default = None
            self.config = self._getconfig(ctrl, storage), self._setconfig(ctrl, storage)

    @staticmethod
    def globals(ctrl):
        "returns access to globals"
        return ctrl.getGlobal('css').last.path

    @staticmethod
    def storedpaths(ctrl, name, exts) -> List[Path]:
        "returns a stored path"
        cnf = ctrl.getGlobal('css').last.path
        fcn = lambda i: cnf[i].get(default = None)

        pot = [fcn(i.replace('.', '')) for _, i in exts]
        if name is not None:
            pot.insert(0, fcn(name))

        pot = [i for i in pot if i is not None]
        return [Path(i) for i in pot]

    @staticmethod
    def firstexistingpath(pot: List[Path]) -> Optional[str]:
        "selects the first existing path from a list"
        return next((str(i) for i in pot if i.exists()),
                    next((str(i.parent) for i in pot if i.parent.exists()), # type: ignore
                         None))

    @staticmethod
    def firstexistingparent(pot: List[Path]) -> Optional[str]:
        "selects the first existing path from a list"
        return next((str(i) for i in pot if i.parent.exists()), None) # type: ignore

    @classmethod
    def _getconfig(cls, ctrl, storage = None):
        def _get(ext, bopen):
            if bopen:
                return cls.firstexistingpath(cls.storedpaths(ctrl, storage, ext))
            return cls.firstexistingparent(cls.storedpaths(ctrl, storage, ext))
        return _get

    @classmethod
    def _setconfig(cls, ctrl, storage = None):
        cnf = cls.globals(ctrl)
        def _defaultpath(rets, bcheck: bool = True):
            vals  = {} # type: Dict[str, str]
            itr   = (rets,) if isinstance(rets, str) else rets
            first = None
            for ret in itr:
                ret = Path(ret)
                if bcheck:
                    if not ret.exists():
                        continue
                    ret = ret.resolve()

                if cnf.get(ret.suffix[1:], default = _m_none) is not _m_none:
                    vals.setdefault(ret.suffix[1:], str(ret))
                if first is None:
                    first = ret
            if storage is not None:
                vals[storage] = str(first)
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

    def _parse_path(self, info:dict, bopen):
        if self.config is None:
            return

        path = self.config[0](info[self._KFT], bopen)
        if path is not None:
            apath = Path(path)
            if apath.is_dir():
                info['initialdir']  = path
            else:
                info['initialdir']  = str(apath.parent)
                info['initialfile'] = str(apath.name)

    def _parse_all(self, bopen):
        info = {key: getattr(self, key)
                for key in self.__dict__
                if getattr(self, key) is not None and key[0] != '_'}
        info.pop('config', None)

        self._parse_filetypes(info)
        self._parse_extension(info)
        self._parse_path(info, bopen)
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

        if self.config is not None and self.config[1] is not None:
            self.config[1](rets, dialog is _tkopen)
        return rets

    def open(self):
        "Returns a filepath to be opened."
        return self._tk_run(self._parse_all(True), _tkopen)

    def save(self):
        "Returns a filepath where to save to."
        info = self._parse_all(False)
        info.pop('multiple', None)
        return self._tk_run(info, _tksave)
