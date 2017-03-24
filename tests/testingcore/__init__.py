#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" access to files """
from typing  import Union, Sequence
from pathlib import Path

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

def path(name:str) -> Union[str, Sequence[str]]:
    u"returns the path to the data"
    default = PATHS.get(name.lower().strip(), name)
    if callable(default):
        return default()

    def _test(i):
        val = Path("../tests/"+__package__+"/"+i)
        if not val.exists():
            raise KeyError("Check your file name!!! {}".format(val))
        return str(val.resolve())

    if isinstance(default, tuple):
        return tuple(_test(i) for i in default)
    else:
        return _test(default)

def getmonkey():
    u"for calling with pudb"
    import  pytest  # pylint: disable=unused-import,unused-variable
    from    _pytest.monkeypatch import MonkeyPatch
    import  warnings
    warnings.warn("Unsafe call to MonkeyPatch. Use only for manual debugging")
    return MonkeyPatch()
