#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'The names of the different rules'
from typing import Dict

NAMES: Dict[str, str] = dict(
    saturation = 'non-closing',
    population = '% good',
    hfsigma    = 'σ[HF]',
    extent     = 'Δz',
    pingpong   = '∑|dz|',
    clipping   = 'z ∉ range(φ₁ → φ₃)',
)
