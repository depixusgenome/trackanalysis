#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows FoV stats"
from   typing                  import List, Tuple, ClassVar, Set

import pandas as pd

from   data.trackops           import trackname
from   ._plot                  import _WhiskerBoxPlot
from   ._utils                 import concat as _concat

class _BeadStatusPlot(_WhiskerBoxPlot):
    _bead:  pd.DataFrame
    _NAME:  ClassVar[str]       = 'beadstatus'
    _XAXIS: ClassVar[Set[str]]  = {'track', 'tracktag', 'beadstatus'}
    _YAXIS: ClassVar[str]       = 'bead'
    _COLS:  ClassVar[List[str]] = ['track', 'tracktag', 'trackid', 'bead']

    def _select(self) -> Tuple[List[str], str, pd.DataFrame]:
        xaxis = [i for i in self._model.theme.xaxis if i in self._XAXIS]
        return self._find_df(xaxis, self._YAXIS)

    def compute(self):
        "compute base dataframes"
        out: List[pd.DataFrame] = [self._bead] if hasattr(self, '_bead') else []

        itr = self._computations('_bead', (Exception, pd.DataFrame), False)
        for proc, info in itr:
            data = pd.DataFrame({
                'track': [trackname(proc.model[0])],
                self._NAME: (
                    info.errkey() if isinstance(info, Exception) else
                    'bug'         if not isinstance(info, pd.DataFrame) else
                    'ok'          if info.shape[0] else
                    'empty'
                )
            })
            out.append(self._compute_update(itr.send(data), 1.))

        if not out:
            return

        self._bead = _concat(out)
        self._bead = self._compute_tags(self._bead)
