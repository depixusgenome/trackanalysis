#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"See all beads together"
from typing                            import (Dict, Optional, List, Tuple, Set,
                                               cast, TYPE_CHECKING)
from itertools                         import product
import numpy                           as     np

from model.plots                       import PlotTheme, PlotModel, PlotDisplay, PlotAttrs
from peakfinding.processor.__config__  import PeakSelectorTask
from taskmodel                         import InstrumentType
from utils                             import initdefaults
from utils.array                       import EventsArray, EVENTS_DTYPE
from .._model                          import PeaksPlotModelAccess, PeaksPlotTheme
from .._peakinfo                       import (PeakInfoModelAccess as _PeakInfoModelAccess,
                                               IdentificationPeakInfo, StatsPeakInfo)
from ..cyclehistplot                   import HistPlotTheme

Output = Dict[int, Tuple[List[np.ndarray], Dict[str, np.ndarray]]]


class PeakInfoModelAccess(_PeakInfoModelAccess):
    "Limiting the info to extract from all peaks"
    _CLASSES = [IdentificationPeakInfo(), StatsPeakInfo()]

    def __init__(self, mdl, bead):
        super().__init__(mdl, bead, self._CLASSES)

    def sequences(self):
        "return the sequences available"
        key = self.sequencekey
        return {} if key is None else {key: self._model.sequences(key)}

    def hybridisations(self):
        "returns the peaks for a single sequence"
        key = self.sequencekey
        seq = self._model.hybridisations(key)
        return {} if seq is None else {key: seq}

class HairpinGroupScatterTheme(PlotTheme):
    "grouped beads plot theme"
    name       = "hairpingroup.plot"
    figsize    = PlotTheme.defaultfigsize(500, 300)
    xlabel     = 'Bead'
    ylabel     = 'Bases'
    reflabel   = 'Hairpin'
    xgridalpha = 0.
    ntitles    = 5
    format     = '0.0'
    events     = PlotAttrs('~gray', 'o', 3,  alpha      = .5)
    peaks      = PlotAttrs('~blue', 'o', 10, line_alpha = 1., fill_alpha = .0)
    hpin       = PlotAttrs('color', '+', 15, alpha      = 1., line_width = 2)
    pkcolors   = {
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
    displaytimeout = .5

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class HairpinGroupScatterModel(PlotModel):
    "grouped beads plot model"
    theme   = HairpinGroupScatterTheme()
    display = PlotDisplay(name = "hairpingroup.plot")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class HairpinGroupHistTheme(PlotTheme):
    "grouped beads plot theme"
    name     = "hairpingroup.plot.hist"
    figsize  = PlotTheme.defaultfigsize(300, 300)
    xdata    = "duration"
    binsize  = .1
    xlabel   = PeaksPlotTheme.xtoplabel
    ylabel   = 'Density'
    hist     = PlotAttrs('~gray', '┸', 1, fill_color = 'gray')
    toolbar  = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,reset,save'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class HairpinGroupHistModel(PlotModel):
    "grouped beads plot model"
    theme   = HairpinGroupHistTheme()
    display = PlotDisplay(name = "hairpingroup.plot.hist")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class HairpinGroupStore:
    "info used for grouping beads"
    def __init__(self):
        self.name:      str                 = "hairpingroup"
        self.discarded: Dict[str, Set[int]] = {}

class HairpinGroupModelAccess(PeaksPlotModelAccess):
    "task acces to grouped beads"
    def __init__(self):
        super().__init__()
        self.__store  = HairpinGroupStore()

    def swapmodels(self, ctrl) -> bool:
        "swap models for those in the controller"
        if super().swapmodels(ctrl):
            self.__store = ctrl.display.swapmodels(self.__store)
            return True
        return False

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
        self._updatedisplay(store, discarded = info)

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
            cache = self._tasksdisplay.cache(-1)()
            if not cache:
                return {}
            cache = dict(cache)

        cache = {i: j for i, j in cache.items()
                 if not isinstance(j, Exception) and j[1] is not None}
        bead  = self.bead
        for i in self.discardedbeads:
            if i != bead:
                cache.pop(i, None)

        if not cache:
            return {}

        seq = self.sequencekey
        if seq is not None and self.oligos:
            best  = lambda y: min(y, default = None, key = lambda x: y[x][0])  # noqa
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

    def runbead(self) -> Optional[Output]:  # type: ignore
        "collects the information already found in different peaks"
        super().runbead()
        cache = self._tasksdisplay.cache(-1)()
        if cache is None:
            return None

        cache = dict(cache)
        beads = self.displayedbeads(cache)
        if not beads:
            return None

        tsk         = cast(PeakSelectorTask, self.peakselection.task)
        out: Output = {}
        bead        = self.bead
        keyfcn      = lambda x: -1000 if x[0] == bead else x[0]  # noqa
        for bead, params in sorted(beads.items(), key = keyfcn):
            itms      = tuple(tsk.details2output(cache[bead][1]))
            out[bead] = [], PeakInfoModelAccess(self, bead).createpeaks(itms)
            out[bead][0].extend(cache[bead][1].positions)

            if len(out[bead][0]):
                evts = (np.concatenate(out[bead][0])-params[1])*params[0]
            else:
                evts = []
            out[bead] = evts, out[bead][1]
        return out

class ConsensusScatterTheme(PlotTheme):
    "scatter plot of durations & rates thee"
    name       = "consensus.plot.scatter"
    figsize    = PlotTheme.defaultfigsize(300, 300)
    xlabel     = PeaksPlotTheme.xlabel
    ylabel     = PeaksPlotTheme.xtoplabel
    reflabel   = 'Hairpin'
    format     = '0.0'
    peaks      = PlotAttrs('color', '+', 10, line_alpha = 1., fill_alpha = .0)
    pkcolors   = {
        'dark':  {'missing': 'red', 'found': 'lightgreen'},
        'basic': {'missing': 'red', 'found': 'darkgreen'}
    }
    toolbar  = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,reset,save,hover,box_select'
    tooltipmode      = 'mouse'
    tooltippolicy    = 'follow_mouse'
    tooltips         = [('Bead',                   '@bead'),
                        ('Z (base)',               '@bases'),
                        ('Strand',                 '@orient'),
                        (PeaksPlotTheme.xlabel,    '@rate{0.0}'),
                        (PeaksPlotTheme.xtoplabel, '@duration{0.000}')]

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class ConsensusScatterModel(PlotModel):
    "scatter plot of durations & rates model"
    theme   = ConsensusScatterTheme()
    display = PlotDisplay(name = "consensus.plot.scatter")

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class ConsensusHistPlotTheme(HistPlotTheme):
    "consensus plot plot model: histogram"
    name             = "consensus.plot.hist"
    figsize          = PlotTheme.defaultfigsize(300, 300)
    xlabel           = 'Bead Count'
    minzoomz         = None
    toolbar          = dict(PlotTheme.toolbar)
    toolbar['items'] = 'ypan,ybox_zoom,reset,save,hover,ybox_select'
    tooltips         = HistPlotTheme.tooltips[:-1]+[('Detection (%)', '@nbeads{0}')]
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class ConsensusHistPlotModel(PlotModel):
    "consensus plot plot model: histogram"
    theme   = ConsensusHistPlotTheme()
    display = PlotDisplay(name = "consensus.plot.hist")

class ConsensusConfig:
    "consensus bead config"
    def __init__(self):
        self.name      = "consensus"
        args           = {"align": None, "peakalign": None}
        self.picotwist = PeakSelectorTask(rawfactor = 2., **args)
        self.sdi       = PeakSelectorTask(rawfactor = 1., **args)
        self.muwells   = PeakSelectorTask(rawfactor = 4., **args)

    def __getitem__(self, name) -> PeakSelectorTask:
        return getattr(self, InstrumentType(name).name)

    def __setitem__(self, name, value: PeakSelectorTask):
        setattr(self, InstrumentType(name).name, value)

class ConsensusModelAccess(HairpinGroupModelAccess):
    "task acces to grouped beads"
    if TYPE_CHECKING:
        instrument: str

    def __init__(self):
        super().__init__()
        self.__config = ConsensusConfig()

    def swapmodels(self, ctrl) -> bool:
        "swap models for those in the controller"
        if super().swapmodels(ctrl):
            self.__config = ctrl.display.swapmodels(self.__config)
            return True
        return False

    def consensuspeaks(self, dtl):
        "peaks for the consensus bead"
        stats = self.__consensuspeakinfo()
        out   = self.__consensuspeakstats(dtl, stats)
        self.__consensuspeakid(out)

        allinfo = {
            i: np.concatenate([j[i] for j in stats.values()])
            for i in next(iter(stats.values()), {})
        }

        if not allinfo:
            allinfo = PeakInfoModelAccess(self, self.bead).createpeaks([])
        else:
            allinfo['bead'] = np.concatenate(
                [np.full(len(j['bases']), i, dtype = 'i4') for i, j in stats.items()]
            )

        kern = self.__config[self.instrument].histogram.kernelarray()
        cnv  = {'pos': 'bases', 'bases': 'peaks', 'basesstd': 'peaksstd'}
        return {cnv.get(i, i): j for i, j in out.items()}, allinfo, kern[kern.size//2]

    def runbead(self) -> Optional[Output]:  # type: ignore
        "collects the information already found in different peaks"
        track = self.track
        if track is None:
            return None

        PeaksPlotModelAccess.runbead(self)
        cache = self._tasksdisplay.cache(-1)()
        if cache is None:
            return None

        cache = dict(cache)
        beads = self.displayedbeads(cache)
        if not beads:
            return None

        arr   = []
        for bead, rho in beads.items():
            evts = (cache[bead][1].positionsperpeak()['events']-rho[1])*rho[0]
            arr.append(EventsArray(list(enumerate(evts)), dtype = EVENTS_DTYPE))

        prec = self.__config[self.instrument].precision
        if prec is None:
            prec = np.nanmedian([track.rawprecision(i)*rho[0] for i, rho in beads.items()])
        dtl  = self.__config[self.instrument].detailed(arr, precision = prec)
        return dtl

    def __consensuspeakinfo(self) -> Dict[int, Dict[str, np.ndarray]]:
        if self.roottask is None:
            return {}
        cache = self._tasksdisplay.cache(-1)()
        assert cache is not None
        beads = set(self.displayedbeads(cache))
        fcn   = cast(PeakSelectorTask, self.peakselection.task).details2output
        return {
            i: PeakInfoModelAccess(self, i).createpeaks(tuple(fcn(cache[i][1])))
            for i in beads
        }

    @staticmethod
    def __consensuspeakstats(dtl, stats) -> Dict[str, np.ndarray]:
        out: Dict[str, List[float]] = {
            **{i:   [] for i in ('pos', 'nbeads')},
            **{i+j: [] for i, j in product(('count', 'duration', 'bases'), ('', 'std'))},
        }
        if dtl is None:
            return out

        for peak, beadpeaks in dtl.output('nanmean'):
            tmp: Dict[str, List[np.ndarray]]
            tmp    = {'count': [], 'duration': [], 'bases': []}
            nbeads = 0
            for data, evts in zip(stats.values(), beadpeaks):
                evts    = [np.max(k['data']) for k in evts]
                bases   = np.searchsorted(data['bases'], evts)-1

                nbeads += len(bases) > 0
                for j, k in tmp.items():
                    k.append(data[j][bases])

            out['nbeads'].append(nbeads*100/max(1, len(dtl.events)))
            out['pos'].append(peak)
            for j, k in tmp.items():
                arr = np.concatenate(k)
                out[j].append(arr.mean())
                out[j+'std'].append(arr.std())
        return {i: np.array(j, dtype = 'f4') for i,j in out.items()}

    def __consensuspeakid(self, out: Dict[str, np.ndarray]):
        info = PeakInfoModelAccess(self, self.bead)
        out.update(
            id       = np.full(len(out['pos']), np.NaN, dtype = 'f4'),
            distance = np.full(len(out['pos']), np.NaN, dtype = 'f4'),
            orient   = IdentificationPeakInfo.defaultstrand(info, out['pos'])
        )
        if not out or len(out['pos']) == 0 or self.sequencekey is None:
            return

        fcn   = self.identification.attribute('match', self.sequencekey).pair
        tmp   = fcn(out['pos'], 1., 0)['key']
        good  = tmp >= 0

        out['id'][good]       = tmp[good]
        out['distance'][good] = (tmp - out['pos'])[good]
        out['orient']         = IdentificationPeakInfo.strand(
            info,
            self.sequences(self.sequencekey),
            self.hybridisations(self.sequencekey),
            out['id'],
            out['bases']
        )
