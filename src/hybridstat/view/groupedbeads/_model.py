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

class GroupedBeadsScatterTheme(PlotTheme):
    "grouped beads plot theme"
    name     = "groupedbeads.plot"
    figsize  = PlotTheme.defaultfigsize(800, 350)
    xlabel   = 'Bead'
    ylabel   = 'Bases'
    reflabel = 'Hairpin'
    ntitles  = 5
    format   = '0.0'
    events   = PlotAttrs({"dark": 'lightblue', 'basic': 'darkblue'},   'circle',
                         3, alpha = .5)
    peaks    = PlotAttrs(dict(events.color), 'diamond', 10, alpha = .5)
    hpin     = PlotAttrs('color', 'cross', 15, alpha = 1., line_width=2)
    pkcolors = {
        'dark':  {'missing': 'red', 'found': 'lightgreen'},
        'basic': {'missing': 'red', 'found': 'darkgreen'}
    }
    toolbar  = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,reset,save,hover'
    tooltipmode      = 'mouse'
    tooltippolicy    = 'follow_mouse'
    tooltips         = [('Bead', '@bead'),
                        ('Z (base)', '@bases'),
                        ('Ref (base)', '@id'),
                        (PeaksPlotTheme.xlabel,    '@count{0.0}'),
                        (PeaksPlotTheme.xtoplabel, '@duration{0.000}')]

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class GroupedBeadsScatterModel(PlotModel):
    "grouped beads plot model"
    theme   = GroupedBeadsScatterTheme()
    display = PlotDisplay(name = "groupedbeads.plot")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class GroupedBeadsHistTheme(PlotTheme):
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

class GroupedBeadsHistModel(PlotModel):
    "grouped beads plot model"
    theme   = GroupedBeadsHistTheme()
    display = PlotDisplay(name = "groupedbeads.plot.hist")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class GroupedBeadsStore:
    "info used for grouping beads"
    def __init__(self):
        self.name:      str                 = "groupedbeads"
        self.discarded: Dict[str, Set[int]] = {}

Output = Dict[int, Tuple[List[np.ndarray], Dict[str, np.ndarray]]]
class GroupedBeadsModelAccess(PeaksPlotModelAccess):
    "task acces to grouped beads"
    __store = Indirection()
    def __init__(self, ctrl, addto = False):
        super().__init__(ctrl, addto = addto)
        self.__store = GroupedBeadsStore()

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

    def runbead(self) -> Optional[Output]: # type: ignore
        "collects the information already found in different peaks"
        super().runbead()
        cache = self._ctrl.tasks.cache(self.roottask, -1)()
        if cache is None:
            return None

        cache = {i: j for i, j in cache.items() if not isinstance(j, Exception)}
        if len(cache) == 0:
            return None

        seq   = self.sequencekey
        if seq is not None and self.oligos:
            best  = lambda y: min(y, default = None, key = lambda x: y[x][0])
            beads = {i: self.getfitparameters(seq, i)
                     for i, (j, _) in cache.items()
                     if best(getattr(j, 'distances', [])) == seq or i == self.bead}
        else:
            beads = {i: self._defaultfitparameters(i, j)
                     for i, j in cache.items() if j[1] is not None}

        if len(beads) == 0:
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
