#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"See all beads together"
from typing                 import Dict, Optional, List, Tuple, Set, cast
import numpy as np

from control.decentralized  import Indirection
from model.plots            import PlotTheme, PlotModel, PlotDisplay, PlotAttrs
from utils                  import initdefaults
from .._model               import PeaksPlotModelAccess, PeakSelectorTask, PeaksPlotTheme
from .._peakinfo            import createpeaks as _createpeaks

class GroupedBeadsScatterTheme(PlotTheme):
    "grouped beads plot theme"
    name     = "groupedbeads.plot"
    figsize  = PlotTheme.defaultfigsize(800, 350)
    xlabel   = 'Bead'
    ylabel   = 'Bases'
    reflabel = 'Hairpin'
    ntitles  = 5
    format   = '0.0'
    events   = PlotAttrs({"dark": 'lightblue', 'basic': 'darkblue'},   'circle', .1)
    peaks    = PlotAttrs({"dark": 'lightgreen', 'basic': 'darkgreen'}, 'diamond', .1)
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
    def discardedbeads(self) -> List[int]:
        "return discarded beads for the given sequence"
        return self.__store.discarded.get(self.sequencekey, [])

    @discardedbeads.setter
    def discardedbeads(self, values):
        "sets discarded beads for the given sequence"
        store = self.__store
        info  = dict(store.discarded)
        info[self.sequencekey] = list(values)
        self._ctrl.display.update(store, discarded = info)

    def runbead(self) -> Optional[Output]: # type: ignore
        "collects the information already found in different peaks"
        super().runbead()
        cache = self._ctrl.tasks.cache(self.roottask, -1)()
        if cache is None:
            return None

        cache = {i: j for i, j in cache.items() if not isinstance(j, Exception)}
        if len(cache) == 0:
            return None

        seq = self.sequencekey
        if seq is None:
            beads = set(cache)
        else:
            beads = set()
            best  = lambda y: max(y, default = None, key = lambda x: y[x][0])
            beads = {i for i, (j, _) in cache.items() if best(j.distances) == seq}

        if len(beads) == 0:
            return None

        tsk         = cast(PeakSelectorTask, self.peakselection.task)
        out: Output = {}
        for bead in beads:
            itms      = tuple(tsk.details2output(cache[bead][1]))
            out[bead] = ([], _createpeaks(self, itms))
            for _, evts in itms:
                evts = [np.nanmean(np.concatenate(i['data'])) for i in evts]
                out[bead][0].append(np.array(evts, dtype = 'f4'))
        return out
