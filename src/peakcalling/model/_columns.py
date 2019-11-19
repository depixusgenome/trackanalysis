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
    Column('tp',           'y', None, True,  True,  True,  'identified (% bindings)'),
    Column('fn',           'y', None, True,  True,  True,  'missing (% bindings)'),
    Column('fpperbp',      'y', None, True,  True,  True,  'unidentified (bp⁻¹)'),
    Column('fnperbp',      'y', None, True,  True,  True,  'missing (bp⁻¹)'),
    Column('toptp',        'y', None, True,  True,  True,  'top strand identified (% bindings)'),
    Column('topfn',        'y', None, True,  True,  True,  'top strand missing (% bindings)'),
    Column('bottomtp',     'y', None, True,  True,  True,  'bottom strand identified (% bindings)'),
    Column('bottomfn',     'y', None, True,  True,  True,  'bottom strand missing (% bindings)'),
    Column('stretch',      'y', None, True,  True,  False, 'stretch (bp/µm)'),
    Column('bias',         'y', None, True,  True,  False, 'bias (µm)'),
    Column('strandsize',   'y', None, True,  True,  False, 'strand size (µm)'),
    Column('hairpin',      'x', None, True,  True,  False, 'hairpin'),
    Column('distance',     'y', None, True,  False, False, 'Δ(binding - blockage) (bp)'),
    Column('closest',      'x', None, True,  False, False, 'binding (bp)'),
    Column('orientation',  'x', None, True,  False, False, 'strand'),
    Column('binnedz',      'x', None, False, False, True,  'z (µm)'),
    Column('binnedbp',     'x', None, True,  False, True,  'z (bp)'),
    Column('peakposition', 'y', None, False, False, False, 'z (µm)'),
    Column('baseposition', 'y', None, True,  False, False, 'z (bp)'),
    Column('hfsigma',      'y', 'stretch', False, True,  False, 'σ[HF] (bp)'),
    Column('nblockages',   'y', None,      False, True,  False, 'blockage count'),
    Column('bead',         'y', None,      False, True,  False, 'count (%)'),
    Column('tracktag',     'x', None,      False, True,  False, 'track group'),
    Column('track',        'x', None,      False, True,  False, 'track'),
    Column('blockageresolution', 'y', 'stretch', False, False, False, 'σ[blockage] (bp)'),
    Column('hybridisationrate',  'y', 100.,      False, False, False, 'hybridisation rate (%)'),
    Column('averageduration',    'y', None,      False, False, False, 'binding duration (s)'),
    Column('status',             'x', None,      False, False, False, 'blockage status'),
    Column('blockagehfsigma',    'y', 'stretch', False, False, False, 'σ[HF] per blockage (bp)'),
    Column('beadstatus',         'x', None,      False, True,  True,  'bead status'),

    # next are needed for identification, not displays, thus have no labels
    Column('trackid',            'x', None, False, True, False, None),
    Column('bead',               'x', None, False, True, False, None),
})
