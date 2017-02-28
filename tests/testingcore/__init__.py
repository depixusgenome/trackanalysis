#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" access to files """
import os

PATHS = dict(small_pickle   = "small_pickle.pk",
             small_legacy   = "test035_5HPs_mix_GATG_5nM_25C_8sec_with_ramp.trk",
             big_legacy     = "test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk",
             big_grlegacy   = "test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec",
             ramp_legacy    = "ramp_5HPs_mix.trk")

def path(name:str) -> str:
    u"returns the path to the data"
    val = "../tests/"+__package__+"/"+PATHS.get(name.lower().strip(), name)
    if not os.path.exists(val):
        raise KeyError("Check your file name!!! "+val)
    return os.path.abspath(val)
