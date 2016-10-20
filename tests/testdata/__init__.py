#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" access to files """
import os

PATHS = dict(small_legacy = "test035_5HPs_mix_GATG_5nM_25C_8sec_with_ramp.trk",
             big_legacy   = "test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk")

def path(name:str) -> str:
    u"returns the path to the data"
    val = "../tests/testdata/"+PATHS.get(name.lower().strip(), name)
    if not os.path.exists(val):
        raise KeyError("Check your file name!!!")
    return val
