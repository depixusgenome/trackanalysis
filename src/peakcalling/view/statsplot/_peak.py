#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows FoV stats for peaks only"
from   typing   import List, Tuple, Generator

import pandas as pd

from   ...model import COLS
from   ._plot   import _WhiskerBoxPlot
from   ._utils  import binnedz as _binnedz, concat as _concat, _IDS

class _PeaksPlot(_WhiskerBoxPlot):
    _bead: pd.DataFrame
    _peak: pd.DataFrame

    def _select(self) -> Tuple[List[str], str, pd.DataFrame]:
        xaxis = [
            i
            for i in self._model.theme.xaxis
            if not any(j.key == i and j.fit for j in COLS)
        ]
        if not xaxis:
            xaxis = ['track']
        yaxis = self._model.theme.yaxis
        if any(j.key == yaxis and j.fit for j in COLS):
            yaxis = 'hybridisationrate'
        return self._find_df(xaxis, yaxis)

    def compute(self, _: bool):
        "compute base dataframes"
        cols: List[str] = list({
            i.key for i in COLS if i.raw and not i.fit and i.key != 'nblockages'
        })
        itr:  Generator = self._computations('_peak')
        lst:  List[pd.DataFrame] = [self._peak] if hasattr(self, '_peak') else []
        lst.extend(
            self._compute_update(itr.send(info.reset_index())[cols], self._model.theme.stretch)
            for _, info in itr
        )

        if lst:
            self._peak = _concat(lst)
            _binnedz(self._model.theme.binnedz, self._peak)

            tag:  str  = self._model.theme.statustag['']
            self._bead = (
                self._peak
                .groupby(_IDS).agg(
                    **{
                        i: (i, 'first')
                        for i in self._peak.columns
                        if any(j.key == i and j.perbead and j.key not in _IDS for j in COLS)
                    },
                    nblockages = ('status',  lambda x: (x == tag).sum())
                ).reset_index()
            )

            self._bead = self._compute_tags(self._bead)
            self._peak = self._compute_tags(self._peak)

        elif hasattr(self, '_peak'):
            del self._peak
