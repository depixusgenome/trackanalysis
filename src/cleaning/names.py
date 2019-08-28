#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'The names of the different rules'
from typing import Dict

NAMES: Dict[str, str] = dict(
    aberrant   = 'outlier',
    saturation = 'non-closing',
    population = '% good',
    hfsigma    = 'σ[HF]',
    extent     = 'Δz',
    pingpong   = '∑|dz|',
    phasejump  = 'SDI phase-jumps',
    clipping   = 'z ∉ range(φ₁ → φ₃)',
    alignment  = 'alignment',
)
