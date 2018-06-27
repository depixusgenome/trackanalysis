#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds shortcuts for using holoview"
import numpy             as     np
from   utils.holoviewing import hv, BasicDisplay
from   data.track        import Track, isellipsis # pylint: disable=unused-import

class RampDisplay(BasicDisplay, ramp = Track):
    """
    Displays ramps

    Keywords are:

    * *beads*: the list of bead to display
    * *cycles*: the list of cycles to display
    * *align*: can be

        * *first*:   align all cycles on their 1st values
        * *last*:  align all cycles on their last values
        * *max*:    align all cycles around their *zmag* max position
        * *None*: don't align cycles

    * *alignmentlength*: if *align* is not *None*, will use this number of
    frames for aligning cycles
    * *legend*: legend position, *None* for no legend
    """
    _beads           = None
    _cycles          = None
    _align           = 'max'
    _alignmentlength = 5
    _stretch         = 1.
    _bias            = 0.

    def __getitem__(self, values):
        if isinstance(values, int):
            self._beads = [values]
        elif isinstance(values, list):
            self._beads = values
        elif isinstance(values, tuple):
            beads, cycles = values
            self._beads  = (None     if isellipsis(beads)       else
                            [beads]  if isinstance(beads, int)  else
                            beads)
            self._cycles = (None     if isellipsis(cycles)      else
                            [cycles] if isinstance(cycles, int) else
                            cycles)
        return self

    def getmethod(self): # pylint: disable=too-many-arguments
        if self._cycles is None:
            cycles = ... if self._cycles is None else self._cycles

        items  = self._items.cycles
        zmag   = {i[1]: j for i, j in items['zmag', cycles]}
        length = self._alignmentlength
        if self._align.lower() == 'first':
            imax = dict.fromkeys(zmag.keys(), slice(length))        # type: ignore
        elif self._align.lower() == 'last':
            imax  = dict.fromkeys(zmag.keys(), slice(-length,0))    # type: ignore
        elif self._align.lower() == 'max':
            maxes = {i: int(.1+np.median((j == np.nanmax(j)).nonzero()[0]))
                     for i, j in zmag.items()}
            imax  = {i: slice(max(0, j-length//2), j+length//2) for i, j in maxes.items()}
        else:
            imax  = None

        def _concat(itms, order):
            return np.concatenate([itms[i] if j else [np.NaN] for i in order for j in range(2)])

        def _show(bead):
            data = {i[1]: j for i, j in items[bead,cycles]}
            if imax:
                data = {i: data[i] - np.nanmean(data[i][j]) for i, j in imax.items()}

            zero = np.nanmedian([np.nanmean(j[:length]) for j in data.values()])
            for j in data.values():
                j[:] = (j-zero-self._bias)*self._stretch

            return hv.Curve((_concat(zmag, data), _concat(data, data)),
                            kdims = ['zmag'], vdims = ['z'])
        return _show

    def getredim(self):
        beads = self._items.beads.keys() if self._beads is None else self._beads
        return (('beads', list(beads)),)

__all__ = [] # type: list
