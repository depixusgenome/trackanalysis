#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows FoV stats with hairpin"
from   typing                  import Dict, List, Tuple, ClassVar, FrozenSet

import pandas as pd
import numpy  as np

from   ...model                import COLS
from   ._plot                  import _WhiskerBoxPlot
from   ._utils                 import binnedz as _binnedz, concat as _concat, _IDS

class _HairpinPlot(_WhiskerBoxPlot):
    _bead:    pd.DataFrame
    _peak:    pd.DataFrame
    _RENAMES: ClassVar[Dict[str, str]] = {'hpin': 'hairpin'}
    _BEADOUT: ClassVar[FrozenSet[str]] = frozenset({'closest', 'status'})
    _LINEAR:  ClassVar[FrozenSet[str]] = frozenset(['binnedbp', 'binnedz', 'closest', 'exclusive'])

    def _select(self) -> Tuple[List[str], str, pd.DataFrame]:
        xaxis = self._model.theme.xaxis
        yaxis = self._model.theme.yaxis
        return self._find_df(xaxis, yaxis)

    def compute(self):
        "compute base dataframes"
        perpeakdf:   List[pd.DataFrame] = [self._peak] if hasattr(self, '_peak') else []
        perbeaddf:   List[pd.DataFrame] = [self._bead] if hasattr(self, '_bead') else []
        perpeakcols: List[str]          = list({
            i.key for i in COLS if i.label and not i.perbead and i.raw
        })
        perbeadcols: List[str]          = list({
            *(i.key for i in COLS if i.label and i.perbead and i.raw), *_IDS
        })

        hpin = self._model.display.hairpins
        ori  = self._model.display.orientations
        itr  = self._computations('_bead')
        for _, info in itr:
            info = self.selectbest(hpin, ori, info.reset_index()).rename(columns = self._RENAMES)
            info = itr.send(None if info.shape[0] == 0 else info)
            if info is not None:
                perbeaddf.append(info[perbeadcols])
                perpeakdf.append(
                    self._compute_update(
                        self.resetstatus(
                            self._model.theme.closest,
                            (
                                info.peaks.values[0][perpeakcols]
                                .assign(**{i: info[i].values[0] for i in perbeadcols})
                            )
                        ),
                        info.stretch.values[0]
                    )
                )

        for i, j in (('_peak', perpeakdf), ('_bead', perbeaddf)):
            if j:
                setattr(self, i, _concat(j))
            elif hasattr(self, i):
                delattr(self, i)

        if not hasattr(self, '_peak'):
            return

        _binnedz(self._model.theme.binnedz, self._peak)
        _binnedz(
            self._model.theme.binnedbp, self._peak, 'baseposition', 'binnedbp'
        )

        self.__compute_exclusive()
        self.__compute_statusstats()
        self._bead = self._compute_tags(self._bead)
        self._peak = self._compute_tags(self._peak)

    def __compute_exclusive(self):
        if not hasattr(self, '_peak'):
            return

        self._peak['distance'] = self._peak['closest'] - self._peak['baseposition']
        self._peak['delta']    = self._peak['distance'].abs()

        cols = ['trackid', 'bead', 'closest', 'baseposition']
        self._peak.set_index(cols, inplace = True)
        self._peak['exclusive'] = (
            self._peak
            .groupby(level = cols[:-1])
            .apply(lambda x: x.reset_index()[[*cols[-2:], 'delta']].nsmallest(1, "delta"))
            .reset_index(level = 3, drop = True)
            .set_index(cols[-1], append = True)
            [cols[-2]]
        )
        self._peak.reset_index(inplace = True)

        self._peak['excldistance'] = self._peak['exclusive'] - self._peak['baseposition']
        self._peak['excldelta']    = self._peak['excldistance'].abs()

        # warning: remove the false negatives from following columns only after
        # computing exclusive. Otherwise the latter will not include false negatives
        # as it should
        self._peak.loc[
            self._peak.status == 'falseneg',
            ['distance', 'delta', 'excldistance', 'excldelta']
        ] = np.NaN

    def __compute_statusstats(self):
        if not hasattr(self, '_bead'):
            return

        self._peak = self._peak.assign(**dict.fromkeys(
            (f'f{i}perbp' for i in 'pn'), 0.0
        ))
        self._bead = self._bead.assign(**dict.fromkeys(
            (j+i for i in ('tp', 'fn') for j in ('', 'top', 'bottom')), 0.0
        ))

        self._peak.set_index(['trackid', 'bead'], inplace = True)
        self._bead.set_index(['trackid', 'bead'], inplace = True)

        tags  = ['truepos', 'falsepos', 'falseneg']

        def _set(dframe, col, values, norm):
            dframe.loc[values.index, col] = values / norm.loc[values.index]

        for strand, prefix in (('', ''), ('+', 'top'), ('-', 'bottom')):
            pks = self._peak[~self._peak.closest.isna()]
            if strand != '':
                pks = pks[pks.orientation == strand]

            if pks.shape[0] == 0:
                continue

            cnts  = (
                pks[np.isin(pks.status, tags)]
                .groupby(['status', 'trackid', 'bead'])
                .closest.apply(lambda x: len(x.unique()))
            )

            if cnts.shape[0] == 0:
                continue

            if not any(i in cnts.index.levels[0] for i in ('truepos', 'falsepos')):
                continue

            total = cnts.loc[['truepos', 'falseneg']].groupby(level = [1,2]).sum() / 100

            if 'falseneg' in cnts.index.levels[0]:
                if strand == '':
                    _set(self._peak, 'fnperbp', cnts.loc['falseneg'], self._bead.strandsize)
                _set(self._bead, f'{prefix}fn', cnts.loc['falseneg'], total)

            if strand == '' and 'falsepos' in cnts.index.levels[0]:
                _set(self._peak, 'fpperbp', cnts.loc['falsepos'], self._bead.strandsize)

            if 'truepos' in cnts.index.levels[0]:
                _set(self._bead, f'{prefix}tp', cnts.loc['truepos'], total)

        self._peak.reset_index(inplace = True)
        self._bead.reset_index(inplace = True)
