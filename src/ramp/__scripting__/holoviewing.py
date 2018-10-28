#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds shortcuts for using holoview"
from   functools         import partial
import pandas            as     pd
import numpy             as     np

from   utils.holoviewing import hv, BasicDisplay
from   data.track        import Track, isellipsis # pylint: disable=unused-import
from   ..analysis        import RampAnalysis, RampAverageZTask, RampDataFrameTask

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
    KEYWORDS         = frozenset({i for i in locals() if i[0] == '_' and i[1] != '_'})
    def dataframe(self, percycle = True, **kwa) -> pd.DataFrame:
        """
        return a dataframe containing all info
        """
        if percycle:
            ana = RampAnalysis(dataframetask = RampDataFrameTask(**kwa))
            return ana.dataframe(self._items, self._beads)
        ana = RampAnalysis(averagetask = RampAverageZTask(**kwa))
        return ana.average(self._items, self._beads)

    def status(self, **kwa) -> hv.Table:
        "return the status of the beads"
        info = (self.dataframe(**kwa)
                .groupby("bead")
                .status.first().reset_index()
                .groupby("status")
                .agg({'bead': ('unique', 'count')}).reset_index())
        info.columns = "status", "beads", "count"
        return hv.Table(info, kdims = ["status"], vdims = ["beads", "count"])

    def beads(self, status = "ok", **kwa):
        "return beads which make it through a few filters"
        ana = RampAnalysis(dataframetask = RampDataFrameTask(**kwa))
        return ana.beads(self._items, status, self._beads)

    @staticmethod
    def _name(i):
        if isinstance(i, int):
            return f"bead {i}"
        if isinstance(i, str):
            return i
        assert isinstance(i, tuple) and len(i) == 2
        if i[1] == "":
            assert isinstance(i[0], str)
            return i[0]
        tmp = 'bead ' if isinstance(i[0], int) else ''
        return tmp+f"{i[0]}{('@low', '', '@high')[i[1]]}"

    @staticmethod
    def _crv(data, opts, labl, ind): # pylint: disable=inconsistent-return-statements
        cols = sorted([i for i in data.columns if i.split("@")[0].strip() == ind])
        cols = [hv.Dimension(i, label = labl) for i in cols]
        tmp  = dict(opts)
        if ind == "consensus":
            tmp['style'].pop('color', None)
        ind  = hv.Dimension(ind, label = labl)
        if len(cols) == 1 or len(cols) == 3:
            crv = hv.Curve(data, "zmag", ind, label = ind.name)(**tmp)
        if len(cols) == 1:
            return crv
        if len(cols) == 2:
            return hv.Area(data, "zmag", cols, label = ind.name)(**tmp)
        if len(cols) == 3:
            return hv.Area(data, "zmag", cols[1:], label = ind.name)(**tmp)*crv
        assert False

    def average(self, opts = None, hmap = True, **kwa):
        "return average bead"
        kwa["consensus"] = True
        ana          = RampAnalysis(averagetask = RampAverageZTask(**kwa))
        data         = ana.average(self._items, self._beads)
        data.columns = [self._name(i) for i in data.columns]
        cols         = [i for i in data.columns
                        if not any(j in i for j in ("zmag", "@low", "@high", "consensus"))]
        _crv = partial(self._crv, data,
                       (dict(style = dict(color = "gray", alpha = .25))
                        if opts is None else opts),
                       "bead length(%)" if ana.averagetask.normalize else "z")
        if hmap:
            crvs = {int(i.split()[1]): _crv(i) for i in cols}
            mean = _crv("consensus")
            return (hv.DynamicMap(lambda x: crvs[x]*mean, kdims = ['bead'])
                    .redim.values(bead = list(crvs)))

        return hv.Overlay([_crv(i) for i in cols + ["consensus"]])

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
        zcyc   = self._items.cycles.withdata({0: self._items.secondaries.zmag})
        zmag   = {i[1]: j for i, j in zcyc}
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
            imax  = None # type: ignore

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
        return (('bead', list(beads)),)

__all__ = [] # type: list
