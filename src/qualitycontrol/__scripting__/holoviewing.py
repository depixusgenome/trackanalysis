#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds quality control displays
"""
from   typing                        import List, Dict, cast
from   itertools                     import chain

import numpy                         as     np
import pandas                        as     pd

from   scripting.holoviewing         import hv, ItemsDisplay
from   model.level                   import PHASE
from   data.views                    import isellipsis
from   data.__scripting__.tracksdict import TracksDict # pylint: disable=unused-import

class QualityControl(ItemsDisplay, qc = TracksDict):
    """
    Adds items that should be qc'ed.
    """
    _keys: List[str] = None
    KEYWORDS         = ItemsDisplay.KEYWORDS | frozenset(locals())
    def __getitem__(self, values):
        self._keys = (None   if isellipsis(values)       else
                      values if isinstance(values, list) else
                      [values])
        return self

    @property
    def tracks(self) -> TracksDict:
        "returns selected tracks"
        return self._items[self._keys] if self._keys else self._items

    def secondaries(self, name:str) -> Dict[str, np.ndarray]:
        "returns selected tracks' secondaries"
        name = name.lower()
        return {i: getattr(j.secondaries, name) for i, j in self.tracks.items()}

    def temperatures(self, name = "Tsample", axisrange = (1., 99.)) -> hv.BoxWhisker:
        """
        Temperatures, especially the samples should be within .5°C of one another
        """
        secs   = {i: j['value'] for i, j in self.secondaries(name).items()}
        tolist = lambda i: list(chain.from_iterable(i))
        frame  = pd.DataFrame({'track': tolist([i]*len(j) for i, j in secs.items()),
                               name:    tolist(secs.values())}).dropna()
        rng    = tuple(np.nanpercentile(frame[name], axisrange))
        return (hv.BoxWhisker(frame, "track", name)
                .redim.range(**{name: rng})
                .redim(**{name: hv.Dimension(name, unit = "°C")}))

    def tsample(self, axisrange = (1., 99.)) -> hv.BoxWhisker:
        """
        All sample temperatures should stay within a 0.5°C range
        """
        return self.temperatures("Tsample", axisrange)

    def tsink(self, axisrange = (1., 99.)) -> hv.BoxWhisker:
        """
        All sink temperatures should stay within a 0.5°C range and below 40°C.
        Above 40°C, the Peltiers will be unable to keep the sample at constant
        temperature.
        """
        return self.temperatures("Tsink", axisrange)

    def vcap(self) -> hv.NdOverlay:
        """
        If the same force is applied to all tracks, the `(zmag, vcap)` pairs
        should roughly be aligned on a single downward-slanted line. Values at
        `vcap = 0` can be disregarded as they are outside the sensor's dynamic
        range.
        """
        tolist = lambda i: list(chain.from_iterable(i))
        vcaps  = self.secondaries('vcap')
        frame  = pd.DataFrame({'zmag':  tolist(j['zmag'] for j in vcaps.values()),
                               'vcap':  tolist(j['zmag'] for j in vcaps.values()),
                               'track': tolist([i]*len(j['vcap']) for i, j in vcaps.items())})
        return hv.NdOverlay(hv.Scatter(frame, "zmag", ["vcap", "track"])
                            .groupby("track"))

    def beadextent(self, *beads):
        """
        The extension from phase 1 to phase 3 should be similar for all cycles
        for each bead individually. A drift is an indicator of a drift in zmag
        measures versus the force applied. In such a case, beads will
        behave differently for each cycle.
        """
        return (hv.DynamicMap(self._beadextent, kdims = ['bead'])
                .redim.values(bead = list(beads if beads else self.tracks.commonbeads())))

    def display(self, *beads, **kwa): # pylint: disable=arguments-differ
        """
        Displays all QC graphs.
        """
        return self(**kwa)._display(beads) # pylint:disable=no-member

    # pylint: disable=no-member
    display.__doc__ += (f"""
        Graphs are:

        * `tsample`: {tsample.__doc__}
        * `vcap`: {vcap.__doc__}
        * `beadextent`: {beadextent.__doc__}
        """)
    __doc__          = display.__doc__

    def _beadextent(self, bead):
        act  = lambda _, info: (info[0], np.nanmedian(info[1]))
        extr = lambda i, j: {k[0][1]: k[1] for k in (i.cleancycles[bead, ...]
                                                     .withphases(j)
                                                     .withaction(act))}
        ovr = {}
        dim = hv.Dimension('extents', unit = 'µm')
        for key, track in self.tracks.items():
            if bead in set(track.beadsonly.keys()):
                mins          = extr(track, PHASE.initial)
                maxs          = extr(track, PHASE.pull)
                keys          = sorted(set(mins) & set(maxs))

                extents       = np.full(max(keys)+1, np.NaN, dtype = 'f4')
                extents[keys] = [maxs[i] - mins[i] for i in keys]

                frame         = pd.DataFrame(dict(cycles  = np.arange(len(extents), dtype = 'i4'),
                                                  extents = extents))
            else:
                frame         = pd.DataFrame(dict(cycles  = np.empty(0, dtype = 'i4'),
                                                  extents = np.empty(0, dtype = 'f4')))

            ovr[key] = hv.Curve(frame, 'cycles', dim)

        data = pd.concat([j.data.dropna().assign(track = i) for i, j in ovr.items()])
        miss = list(set(ovr) - set(data.track.unique()))
        data = pd.concat([data, pd.DataFrame({'track': miss, 'extents': [0]*len(miss)})])
        return (hv.BoxWhisker(data, "track", dim)
                +hv.NdOverlay(ovr)(plot = dict(show_grid = True))
               ).cols(1)

    def _display(self, beads):
        stable = [self.tsample(), self.vcap()]
        def _fcn(bead):
            ext = self._beadextent(bead)
            return (stable[0] + stable[1] + ext.BoxWhisker.I + ext.NdOverlay.I).cols(1)
        return (hv.DynamicMap(_fcn, kdims = ['bead'])
                .redim.values(bead = list(beads if beads else self.tracks.commonbeads())))
