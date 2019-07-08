#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds shortcuts for using holoview"
from   functools         import partial
from   typing            import Optional, List, Tuple
import pandas            as     pd
import numpy             as     np

from   utils.array       import popclip
from   utils.holoviewing import hv, BasicDisplay
from   data.track        import Track, isellipsis # pylint: disable=unused-import
from   .analysis         import RampAnalysis, RampConsensusBeadProcessor

class RampDisplay(BasicDisplay, ramp = Track):
    """
    Displays ramps

    Keywords are:

    * *beads*: the list of bead to display
    * *cycles*: the list of cycles to display
    * *align*: an optional alignment task
    * *legend*: legend position, *None* for no legend
    * *alpha*: applies an alpha to all curves
    * *analysis*: a RampAnalysis object used throughout
    """
    _beads:   Optional[List[int]] = None
    _cycles:  Optional[List[int]] = None
    _stretch: float               = 1.
    _bias:    float               = 0.
    _alpha:   float               = .25
    _popclip: Tuple[float, ...]   = (99., .1)
    _tasks:   list                = []
    _analysis: RampAnalysis       = RampAnalysis()
    KEYWORDS         = frozenset({i for i in locals() if i[0] == '_' and i[1] != '_'})
    def dataframe(self, percycle = True, **kwa) -> pd.DataFrame:
        """
        return a dataframe containing all info
        """
        return getattr(
            self._analysis,
            'dataframe' if percycle else 'consensus'
        )(self._items, self._beads, **kwa)

    def status(self, **kwa) -> hv.Table:
        "return the status of the beads"
        status = (
            self.dataframe(**kwa)
            .groupby("bead")
            .status.first().reset_index()
            .groupby("status")
            .bead.unique()
        )

        inds = {i: status.loc[i] for i in status.index.unique()}
        empt = np.empty(0, dtype = 'i4')
        bad  = list(self._items.beads.keys())
        for i in ('ok', 'fixed'):
            bad = np.setdiff1d(bad, inds.get(i, empt))

        info = pd.DataFrame(dict(
            status = ["ok", "fixed", "bad"],
            beads  = [*(inds.get(i, empt) for i in ('ok', 'fixed')), bad]
        ))
        info['count'] = info.beads.apply(len)

        return hv.Table(info, kdims = ["status"], vdims = ["beads", "count"])

    def beads(self, status = "ok", **kwa):
        "return beads which make it through a few filters"
        return self._analysis.beads(self._items, status, self._beads, **kwa)

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
            tmp.pop('color', None)
        ind  = hv.Dimension(ind, label = labl)
        if len(cols) == 1 or len(cols) == 3:
            crv = hv.Curve(data, "zmag", ind, label = ind.name).options(**tmp)
        if len(cols) == 1:
            return crv
        if len(cols) == 2:
            return hv.Area(data, "zmag", cols, label = ind.name).options(**tmp)
        if len(cols) == 3:
            return hv.Area(data, "zmag", cols[1:], label = ind.name).options(**tmp)*crv
        assert False

    def consensus(self, opts = None, hmap = True, normalize = True, **kwa):
        "return average bead"
        data = self.dataframe(False, normalize = normalize, **kwa)
        RampConsensusBeadProcessor.consensus(data, normalize, self.beads("ok"))

        data.columns = [self._name(i) for i in data.columns]
        cols         = [i for i in data.columns
                        if not any(j in i for j in ("zmag", "@low", "@high", "consensus"))]
        _crv = partial(self._crv, data,
                       (dict(color = "gray", alpha = .25)
                        if opts is None else opts),
                       "Z (% bead length)" if normalize else "Z (µm)")
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

        items = self._analysis.beadsview(self._items, *self._tasks)[...,...]

        def _concat(itms):
            return popclip(
                np.concatenate([(i if j else [np.NaN]) for i in itms for j in (0,1)]),
                *self._popclip
            )

        zcid = _concat(self._items.secondaries.cidcycles.values())
        zcyc = _concat(self._items.secondaries.zmagcycles.values())
        zpha = _concat(self._items.secondaries.phasecycles.values())
        def _show(bead):
            try:
                data = _concat([(j-self._bias)*self._stretch  for i, j in items[bead,cycles]])
                exc  = ""
            except Exception as _: # pylint: disable=broad-except
                exc  = str(_)

                data =  np.zeros(len(zcyc))
            info = pd.DataFrame({"zmag": zcyc, "z": data, "phase": zpha, "cycle": zcid})
            crv  = (
                hv.Curve(info, 'zmag', ["z", "phase"])
                .options(alpha = self._alpha, color = "gray")
            )
            return (
                crv
                * crv.to.scatter().opts(color = "phase", cmap ="greens")
                * hv.Text(info.zmag.mean(), .5, exc)
            )
        return _show

    def getredim(self):
        beads = self._items.beads.keys() if self._beads is None else self._beads
        return (('bead', list(beads)),)

__all__ = [] # type: list
