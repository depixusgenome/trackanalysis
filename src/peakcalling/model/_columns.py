#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"dataframe plot cols"
from dataclasses    import dataclass
from typing         import Union, Optional, FrozenSet

INVISIBLE: str            = '\u2063'


@dataclass(eq = True, frozen = True)
class Column:
    "info on a column"
    key:      str
    axis:     str
    factor:   Union[None, float, str]
    fit:      bool
    perbead:  bool
    computed: bool
    label:    Optional[str]

    @property
    def raw(self) -> bool:
        "not computed"
        return not self.computed

def getcolumn(key: str) -> Column:
    "return the column with the given key"
    return next(i for i in COLS if i.key == key)


COLS: FrozenSet[Column] = frozenset({
    Column(*i)
    for i in (
        ('tp',           'y', None, True,  True,  True,  'identified (% bindings)'),
        ('fn',           'y', None, True,  True,  True,  'missing (% bindings)'),
        ('fpperbp',      'y', None, True,  True,  True,  'unidentified (bp⁻¹)'),
        ('fnperbp',      'y', None, True,  True,  True,  'missing (bp⁻¹)'),
        ('toptp',        'y', None, True,  True,  True,  'top strand identified (% bindings)'),
        ('topfn',        'y', None, True,  True,  True,  'top strand missing (% bindings)'),
        ('bottomtp',     'y', None, True,  True,  True,  'bottom strand identified (% bindings)'),
        ('bottomfn',     'y', None, True,  True,  True,  'bottom strand missing (% bindings)'),
        ('stretch',      'y', None, True,  True,  False, 'stretch (bp/µm)'),
        ('bias',         'y', None, True,  True,  False, 'bias (µm)'),
        ('strandsize',   'y', None, True,  True,  False, 'strand size (µm)'),
        ('hairpin',      'x', None, True,  True,  False, 'hairpin'),
        ('closest',      'x', None, True,  False, False, 'closest binding (bp)'),
        ('distance',     'y', None, True,  False, False, 'Δ(closest binding - blockage) (bp)'),
        ('delta',        'y', None, True,  False, True,  'Δ∥closest binding - blockage∥ (bp)'),
        ('exclusive',    'x', None, True,  False, True,  'binding (bp)'),
        ('excldistance', 'y', None, True,  False, True,  'Δ(binding - blockage) (bp)'),
        ('excldelta',    'y', None, True,  False, True,  'Δ∥binding - blockage∥ (bp)'),
        ('orientation',  'x', None, True,  False, False, 'strand'),
        ('binnedz',      'x', None, False, False, True,  'z (µm)'),
        ('binnedbp',     'x', None, True,  False, True,  'z (bp)'),
        ('peakposition', 'y', None, False, False, False, 'z (µm)'),
        ('baseposition', 'y', None, True,  False, False, 'z (bp)'),
        ('hfsigma',      'y', 'stretch', False, True,  False, 'σ[HF] (bp)'),
        ('nblockages',   'y', None,      False, True,  False, 'blockage count'),
        ('saturation',   'y', None,      False, False, False, 'φ₅ saturation'),
        ('bead',         'y', None,      False, True,  False, 'count (%)'),
        ('bead',         'x', None,      False, False, True, 'bead id'),
        ('tracktag',     'x', None,      False, True,  False, 'track group'),
        ('track',        'x', None,      False, True,  False, 'track'),
        ('blockageresolution', 'y', 'stretch', False, False, False, 'σ[blockage] (bp)'),
        ('hybridisationrate',  'y', 100.,      False, False, False, 'hybridisation rate (%)'),
        ('averageduration',    'y', None,      False, False, False, 'binding duration (s)'),
        ('status',             'x', None,      False, False, False, 'blockage status'),
        ('blockagehfsigma',    'y', 'stretch', False, False, False, 'σ[HF] per blockage (bp)'),
        ('beadstatus',         'x', None,      False, True,  True,  'bead status'),

        # next are needed for identification, not displays, thus have no labels
        ('trackid',            'x', None, False, True, False, None),
        ('bead',               'x', None, False, True, False, None),
    )
})
