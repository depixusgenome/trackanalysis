#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"See all beads together"
from typing                 import Dict, Optional, List, Tuple, Set, cast
import numpy as np

from control.decentralized  import Indirection
from model.plots            import PlotTheme, PlotModel, PlotDisplay, PlotAttrs
from utils                  import initdefaults
from .._model               import PeaksPlotModelAccess, PeakSelectorTask, PeaksPlotTheme
from .._peakinfo            import createpeaks as _createpeaks, PeakInfoModelAccess

class HairpinGroupScatterTheme(PlotTheme):
    "grouped beads plot theme"
    name     = "groupedbeads.plot"
    figsize  = PlotTheme.defaultfigsize(950, 550)
    xlabel   = 'Bead'
    ylabel   = 'Bases'
    reflabel = 'Hairpin'
    ntitles  = 5
    format   = '0.0'
    events   = PlotAttrs({"dark": 'lightgray', 'basic': 'darkgray'}, 'circle', 3,
                         alpha = .5)
    peaks    = PlotAttrs({"dark": 'lightblue', 'basic': 'darkblue'}, 'circle', 10,
                         line_alpha = 1.,
                         fill_alpha = .0)
    hpin     = PlotAttrs('color', 'cross', 15, alpha = 1., line_width=2)
    pkcolors = {
        'dark':  {'missing': 'red', 'found': 'lightgreen'},
        'basic': {'missing': 'red', 'found': 'darkgreen'}
    }
    toolbar  = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,reset,save,hover,box_select'
    tooltipmode      = 'mouse'
    tooltippolicy    = 'follow_mouse'
    tooltips         = [('Bead', '@bead'),
                        ('Z (base)', '@bases'),
                        ('Ref (base)', '@id'),
                        (PeaksPlotTheme.xlabel,    '@count{0.0}'),
                        (PeaksPlotTheme.xtoplabel, '@duration{0.000}')]
    displaytimeout = 1.

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class HairpinGroupScatterModel(PlotModel):
    "grouped beads plot model"
    theme   = HairpinGroupScatterTheme()
    display = PlotDisplay(name = "groupedbeads.plot")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class HairpinGroupHistTheme(PlotTheme):
    "grouped beads plot theme"
    name     = "groupedbeads.plot.hist"
    figsize  = PlotTheme.defaultfigsize(300, 300)
    xdata    = "duration"
    binsize  = .1
    xlabel   = PeaksPlotTheme.xtoplabel
    ylabel   = 'Density'
    hist     = PlotAttrs({'dark': 'darkgray', 'basic': 'gray'},
                         'quad', 1, fill_color = 'gray')
    toolbar  = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,reset,save'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class HairpinGroupHistModel(PlotModel):
    "grouped beads plot model"
    theme   = HairpinGroupHistTheme()
    display = PlotDisplay(name = "groupedbeads.plot.hist")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class HairpinGroupStore:
    "info used for grouping beads"
    def __init__(self):
        self.name:      str                 = "groupedbeads"
        self.discarded: Dict[str, Set[int]] = {}

Output = Dict[int, Tuple[List[np.ndarray], Dict[str, np.ndarray]]]
class HairpinGroupModelAccess(PeaksPlotModelAccess):
    "task acces to grouped beads"
    __store = Indirection()
    def __init__(self, ctrl, addto = False):
        super().__init__(ctrl, addto = addto)
        self.__store  = HairpinGroupStore()
        ctrl.theme.updatedefaults("hybridstat.peaks", ncpu = 2)

    @property
    def discardedbeads(self) -> Set[int]:
        "return discarded beads for the given sequence"
        return self.__store.discarded.get(self.sequencekey, set())

    @discardedbeads.setter
    def discardedbeads(self, values):
        "sets discarded beads for the given sequence"
        store = self.__store
        info  = dict(store.discarded)
        info[self.sequencekey] = set(values)
        self._ctrl.display.update(store, discarded = info)

    def _defaultfitparameters(self, bead, itm) -> Tuple[float, float]:
        "return the stretch  & bias for the current bead"
        if itm[0] and itm[0].distances:
            return min(itm[0].distances.values())[1:]
        out = self.identification.constraints(bead)[1:]
        if out[0] is None:
            out = self.peaksmodel.config.estimatedstretch, out[1]
        if out[1] is None:
            out = out[0], itm[1].peaks[0]
        return cast(Tuple[float, float], out)

    def displayedbeads(self, cache = None) -> Dict[int, Tuple[float, float]]:
        "return the displayed beads"
        if not cache:
            cache = self._ctrl.tasks.cache(self.roottask, -1)()
            if not cache:
                return {}
            cache = dict(cache)

        cache = {i: j for i, j in cache.items() if not isinstance(j, Exception)}
        bead  = self.bead
        for i in self.discardedbeads:
            if i != bead:
                cache.pop(i, None)

        if not cache:
            return {}

        seq = self.sequencekey
        if seq is not None and self.oligos:
            best  = lambda y: min(y, default = None, key = lambda x: y[x][0])
            return {
                i: self.getfitparameters(seq, i)
                for i, j in cache.items()
                if best(getattr(j[0], 'distances', [])) == seq or i == self.bead
            }

        return {
            i: self._defaultfitparameters(i, j)
            for i, j in cache.items()
            if j[1] is not None
        }

    def runbead(self) -> Optional[Output]: # type: ignore
        "collects the information already found in different peaks"
        super().runbead()
        cache = self._ctrl.tasks.cache(self.roottask, -1)()
        if cache is None:
            return None

        cache = dict(cache)
        beads = self.displayedbeads(cache)
        if not beads:
            return None

        tsk         = cast(PeakSelectorTask, self.peakselection.task)
        out: Output = {}
        for bead, params in beads.items():
            itms      = tuple(tsk.details2output(cache[bead][1]))
            mdl       = PeakInfoModelAccess(self, bead)
            out[bead] = [], _createpeaks(mdl, itms)
            for _, evts in itms:
                evts = [np.nanmean(np.concatenate(i['data']))
                        for i in evts if len(i['data'])]
                out[bead][0].append(np.array(evts, dtype = 'f4'))

            if len(out[bead][0]):
                evts = (np.concatenate(out[bead][0])-params[1])*params[0]
            else:
                evts = []
            out[bead] = evts, out[bead][1]
        return out
