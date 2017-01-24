#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''
Defines a set of utilitiray functions to analyse ramp data
'''
from . import ramp_module as ramp

def get_beadids_not_closing(data:ramp.RampData,zthreshold:float,acc_ratio:float=0.9):
    u'''
    Given RampData.dataz, computes the zmag closing of all (bead,cycle).
    Returns the ids of beads such that ratio of zmag_close>zthreshold over cycles is below acc_ratio
    '''

    print("zthreshold=",zthreshold)
    zmcl = data.zmagClose(reverse_time=True)
    ratios = (zmcl>zthreshold).mean(axis=1)
    print("ratios",ratios)
    return ratios[ratios < acc_ratio].index.tolist()
