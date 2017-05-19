#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" access to files """
import  json
import  warnings
from    typing  import Union, Sequence, Optional
from    pathlib import Path
import  numpy as np

warnings.filterwarnings('error', category = FutureWarning)
warnings.filterwarnings('error', category = DeprecationWarning)
warnings.filterwarnings('error', category = PendingDeprecationWarning)
np.seterr(all='raise')

def _trackreadertask(fpath, beadsonly = True):
    from model.task     import TrackReaderTask
    from data.trackio   import checkpath
    return TrackReaderTask(path = checkpath(fpath).path, beadsonly = beadsonly)

def big_selected():
    u"returns a TrackReaderTask on 2 GR  files"
    return _trackreadertask((Path(path("big_legacy")).parent/"*.trk",
                             path("CTGT_selection")))

def big_all():
    u"returns a TrackReaderTask on all GR files"
    return _trackreadertask((Path(path("big_legacy")).parent/"*.trk",
                             path("big_grlegacy")))

PATHS = dict(small_pickle   = "small_pickle.pk",
             small_legacy   = "test035_5HPs_mix_GATG_5nM_25C_8sec_with_ramp.trk",
             big_legacy     = "test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk",
             big_grlegacy   = "test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec",
             ramp_legacy    = "ramp_5HPs_mix.trk",
             big_selected   = big_selected,
             big_all        = big_all)

def path(name:Optional[str]) -> Union[str, Sequence[str]]:
    u"returns the path to the data"
    directory = Path("../tests/"+__package__+"/")
    if name is None:
        return str(directory)

    default = PATHS.get(name.lower().strip(), name)
    if callable(default):
        return default()

    def _test(i):
        val = directory/i
        if not val.exists():
            val = Path(i)
            if not val.exists():
                raise KeyError("Check your file name!!! {}".format(val))
        return str(val.resolve())

    if isinstance(default, tuple):
        return tuple(_test(i) for i in default)
    else:
        return _test(default)

def getmonkey():
    u"for calling with pudb"
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category = DeprecationWarning)
        warnings.filterwarnings('ignore', category = PendingDeprecationWarning)
        import  pytest  # pylint: disable=unused-import,unused-variable
        from    _pytest.monkeypatch import MonkeyPatch
        warnings.warn("Unsafe call to MonkeyPatch. Use only for manual debugging")
        return MonkeyPatch()

class DummyPool:
    "DummyPool"
    nworkers = 2
    @staticmethod
    def map(*args):
        "DummyPool"
        return map(*args)
