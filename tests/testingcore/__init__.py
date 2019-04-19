#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" access to files """
from ..testutils import (
        ResourcePath, getmonkey, DummyPool, Path, cast
)

def _trackreadertask(fpath):
    from taskmodel      import TrackReaderTask
    from data.trackio   import checkpath
    return TrackReaderTask(path = checkpath(fpath).path)

def big_selected():
    "returns a TrackReaderTask on 2 GR files"
    return _trackreadertask((Path(cast(str, path("big_legacy"))).parent/"*.trk",
                             path("CTGT_selection")))

def big_all():
    "returns a TrackReaderTask on all GR files"
    return _trackreadertask((Path(cast(str, path("big_legacy"))).parent/"*.trk",
                             path("big_grlegacy")))

PATHS = dict(small_pickle   = "small_pickle.pk",
             small_legacy   = "test035_5HPs_mix_GATG_5nM_25C_8sec_with_ramp.trk",
             big_legacy     = "test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk",
             big_grlegacy   = "test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec",
             ramp_legacy    = "ramp_5HPs_mix.trk",
             smallemdata    = "smallemdata.pk",
             big_selected   = big_selected,
             big_all        = big_all)

path = ResourcePath(None, PATHS) # pylint: disable=invalid-name
