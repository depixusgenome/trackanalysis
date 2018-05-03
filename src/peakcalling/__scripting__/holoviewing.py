#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-ancestors
"Updating PeaksDict for oligo mapping purposes"
from   typing                   import List, Sequence, Tuple, Dict, Callable, Union, cast
from   concurrent.futures       import ProcessPoolExecutor
from   copy                     import deepcopy
from   scipy.interpolate        import interp1d
import numpy                    as np

import sequences

from   utils.holoviewing            import hv, addproperty, displayhook
from   peakfinding.processor        import (PeaksDict,   # pylint: disable=unused-import
                                            SingleStrandProcessor, SingleStrandTask)
from   peakfinding.__scripting__.holoviewing import (PeaksDisplay as _PeaksDisplay,
                                                     PeaksTracksDictDisplay as _PTDDisplay)


from   model.__scripting__          import Tasks
from   cleaning.processor           import DataCleaningException
from   data.__scripting__           import TracksDict   # pylint: disable=unused-import
from   ..processor.fittoreference   import (FitToReferenceProcessor,
                                            FitToReferenceTask,
                                            FitToReferenceDict)
from   ..processor.fittohairpin     import (BEADKEY,    # pylint: disable=unused-import
                                            FitToHairpinDict, Distance)
from   .                            import PeaksTracksDictOperator

displayhook(FitToReferenceDict)
addproperty(FitToReferenceDict, 'display', _PeaksDisplay)

class OligoMappingDisplay(_PeaksDisplay, display = PeaksDict): # type: ignore
    """
    Displays peaks.

    Attributes are:

    * *kdim*: if 'bead', then a *holoviews.DynamicMap* is returned, displaying
    beads independently.
    * *precision* is the noise level used to find peaks
    * *labels*: if *False*, no labels are added. If *None*, labels are added
    if 3 or less beads are shown.
    * *sequence* and *oligo*: can be used to display dna positions. If
    *fit* is *False*, then the returned dynamic map will have *sequence*,
    *stretch* and *bias* widgets as well as *bead*.
    * *stretch* and *bias* values can be provided manually
    * *zero* set to *True* will set the x-axis zero to the first peak position.
    * *fit*: if used in conjunction with *sequence* and *oligo*, each bead
    will be displayed with the best fit sequence.
    * *sequencestyle*, *eventstyle*, *peakstyle* can be used to set the style
    of corresponding graph elements.
    """
    _zero           = True
    _sequence       = None
    _oligos         = None
    _fit            = True
    _reference: str = None
    _sequencestyle  = dict(color = 'gray')
    _reftask        = FitToReferenceTask()
    KEYWORDS        = _PeaksDisplay.KEYWORDS | frozenset(locals())
    def __init__(self, items, **opts):
        super().__init__(items, **opts)
        if self._bias is not None or None not in (self._sequence, self._oligos):
            self._zero = False

    def elements(self, evts, **opts):
        "shows overlayed Curve items"
        if self._reftask and {i for i in evts.keys()} in self._reftask:
            evts = FitToReferenceProcessor.apply(evts, **self._reftask.config())
        return super().elements(evts, **opts)

    def getmethod(self):
        "Returns the method used by the dynamic map"
        if None not in (self._sequence, self._oligos):
            out = _AutoHP(self) if self._fit is True else _ManualHP(self)
            if getattr(out, '_singlestrand') is None:
                setattr(out, '_singlestrand', True)
            return out.run

        return super().getmethod()

    def getredim(self):
        "Returns the keys used by the dynamic map"
        if None not in (self._sequence, self._oligos) and self._fit is not True:
            return _ManualHP(self).getredim()
        return super().getredim()

    def _hpins(self):
        "returns haipin positions"
        opts = deepcopy(self._opts)
        for i, j in self.graphdims().items():
            opts.setdefault(i, j)
        pks   = {}
        if self._labels is True:
            opts['label'] = 'sequence'

        tmp = sequences.peaks(self._sequence, self._oligos)
        if isinstance(tmp, np.ndarray):
            tmp = (('hairpin 1', tmp),)

        for key, vals in cast(Sequence[Tuple[str, np.ndarray]], tmp):
            xvals = np.repeat(vals['position'], 3)
            yvals = np.concatenate([[(0., .1)[plus], (.9, 1.)[plus], np.NaN]
                                    for plus in vals['orientation']])
            pks[key] = hv.Curve((xvals, yvals), **opts)(style = self._sequencestyle)
        return pks

class _AutoHP(OligoMappingDisplay):
    "creates a DynamicMap with fitted oligos"
    _labels = True
    def __init__(self, itms, **kwa):
        super().__init__(itms, **kwa)
        if isinstance(itms, OligoMappingDisplay):
            self.__pins = None
            self.__fits = None
            self.__cache: Dict[BEADKEY, Tuple[str, Distance]] = {}

    def run(self, bead):
        "creates the display"
        if self.__pins is None:
            self.__pins = self._hpins()
            cnf         = dict(sequence = self._sequence,
                               oligos   = self._oligos,
                               fit      = self._fit)
            if self._fit is True:
                cnf.pop('fit')
            self.__fits = self._items.new(FitToHairpinDict, config = cnf)

        cache = self.__cache
        if bead not in cache:
            cache[bead] = min(self.__fits[bead].distances.items(), key = lambda i: i[1][0])
        key, dist = cache[bead]

        tmp = self(stretch = dist.stretch, bias = dist.bias)
        crv = tmp.elements(self._items[[bead]], group = key) # pylint: disable=no-member

        hpc  = self.__pins[key]
        data = np.copy(hpc.data)
        data[:,1] *= np.nanmax(next(iter(crv)).data[:,1])

        pos  = lambda x: .8*np.nanmax(x)+.2*np.nanmin(x)
        pars = np.round(dist.stretch, 1), np.round(dist.bias, 4)
        if pars[1] < 0:
            txt  = f'{hpc.vdims[0]} = {pars[0]}·({hpc.kdims[0]}+{-pars[1]})'
        else:
            txt  = f'{hpc.vdims[0]} = {pars[0]}·({hpc.kdims[0]}-{pars[1]})'
        text = hv.Text(pos(data[:,0]), pos(data[:,1]), txt,
                       kdims = hpc.kdims+hpc.vdims)
        return hv.Overlay(crv+[hpc.clone(data = data), text], group = key)

class _ManualHP(OligoMappingDisplay):
    "Fits per HP"
    _labels = True
    def __init__(self, itms, **kwa):
        super().__init__(itms, **kwa)
        if isinstance(itms, OligoMappingDisplay):
            self.__cache = [None, (), None, ()]
            self.__pins  = self._hpins()

    @staticmethod
    def __clone(itm, stretch, bias):
        data = np.copy(itm.data)
        data[:,0] = (data[:,0]-bias)*stretch
        return itm.clone(data = data)

    def run(self, bead, sequence, stretch, bias):
        "creates the display"
        cache = self.__cache
        if bead != cache[0]:
            cache[0] = bead
            cache[1] = self.elements(self._items[[bead]])
        fcn    = self.__clone
        clones = [fcn(i, stretch, bias) for i in cache[1]]

        if sequence != cache[2]:
            hpc        = self.__pins[sequence]
            data       = np.copy(hpc.data)
            data[:,1] *= np.nanmax(clones[0].data[:,1])
            cache[2]   = sequence
            cache[3]   = [hpc.clone(data = data)]

        return hv.Overlay(clones+cache[3])

    def getredim(self):
        "Returns the method used by the dynamic map"
        values = list(_PeaksDisplay.getredim(self))
        params = tuple((i, getattr(self, '_'+i)) for i in ('stretch', 'bias')
                       if getattr(self, '_'+i) != getattr(self.__class__, '_'+i))
        rngs   = Tasks.getconfig().fittohairpinrange # type: ignore

        pins   = sequences.peaks(self._sequence, self._oligos)
        if isinstance(pins, np.ndarray):
            pins = {'hairpin 1': None}

        values.append(('sequence', sorted(dict(pins).keys())))
        values.extend(params)
        values.extend((i, slice(*rngs[i])) for i in ('stretch', 'bias')
                      if i not in (k for k, _ in params))
        return values

class PeaksTracksDictDisplay(_PTDDisplay, # type: ignore
                             peaks = TracksDict):
    """
    A hv.DynamicMap showing peaks

    Attributes are:
    * *singlestrand* will remove the single-strand peak unless set to `False`
    * *format* == '1d': for a given bead, all tracks are overlayed, For a given
      bead, all tracks are overlayed.  Keywords are:

        * *reference*: the reference is displayed as an area,
        * *distance*: a *HistogramFit* object (default) or *None*. This objects
        computes a stretch and bias which is applied to the x-axis of
        non-reference items.

    * *format* == '2d': for a given bead, all tracks are shown on a 2D
    histogram. Keywords are:

        * *reference*: the reference is displayed as an area,
        * *distance*: a *HistogramFit* object (default) or *None*. This objects
        computes a stretch and bias which is applied to the x-axis of
        non-reference items.

    * *format* == None: keywords are:

        * *reference*: the reference is removed from the *key* widget and
        allways displayed to the left independently.
        * *refdims*: if set to *True*, the reference gets its own dimensions.
        Thus zooming and spanning is independant.
        * *reflayout*: can be set to 'top', 'bottom', 'left' or 'right'
        * *fit*: add stretch & bias sliders
    """
    _singlestrand: Union[SingleStrandTask, bool] = None
    _format       = "2d"
    _reftask      = FitToReferenceTask()
    _refdims      = False
    _peakstyle    = dict(color = 'blue', line_dash = 'dotted')
    _refstyle     = dict(color = 'gray', line_dash = 'dotted')
    _logz         = True
    _loglog       = True
    _textcolor    = 'green'
    _fit          = False
    KEYWORDS      = _PTDDisplay.KEYWORDS | frozenset(locals())
    def __init__(self, items, **opts):
        super().__init__(items, **opts)
        if self._format in ('1d', '2d'):
            self._overlay = 'key'
        elif 'overlay' not in opts:
            self._overlay = None
        if 'reflayout' not in opts:
            self._reflayout = 'same' if self._format is None else 'bottom'

    def _convert(self, kdims, ovrs):
        ovrs = super()._convert(kdims, ovrs)
        ind  = self._refindex(kdims)
        if ind is None or ind >= len(tuple(ovrs)) or len(tuple(ovrs[ind])) == 0:
            return ovrs

        firsts = [next((j for j in i if hasattr(j, 'dpx_label')),
                       next((j for j in i if not isinstance(j, hv.Text)),
                            next(iter(i))))
                  for i in ovrs]
        txt    = [getattr(i, 'dpx_label', None) for i in firsts]
        txt    = [i for i in txt if i]
        if len(txt) == 0 or len(txt) > 4:
            txt = ['']
        elif len(txt) > 1:
            txt = [i.label + ': ' + j for i, j in zip(firsts, txt)]

        ovrs  = list(ovrs)
        first = next(iter(tuple(ovrs[ind])))
        kdims = first.kdims + first.vdims
        minv  = [np.nanmin(first.data[:,k]) for k in range(2)]
        maxv  = [np.nanmax(first.data[:,k]) for k in range(2)]

        ovrs.append(hv.Text(minv[0]*.7+maxv[0]*.3, minv[1]*.3+maxv[1]*.7,
                            '\n'.join(txt), kdims = kdims))
        return hv.Overlay(ovrs)

    def _default_kargs(self, key, bead, kwa):
        super()._default_kargs(key, bead, kwa)
        if self._reference is None or self._reference == key:
            return

        if self._reftask is not None:
            kwa['reftask'] = self._reftask
            if bead not in self._reftask:
                pks = self._items[self._reference].peaks
                if self._singlestrand is not False:
                    if isinstance(self._singlestrand, SingleStrandTask):
                        sstrand = self._singlestrand
                    else:
                        sstrand = Tasks.singlestrand()
                    pks = SingleStrandProcessor.apply(pks[...], **sstrand.config())

                self._reftask.frompeaks(pks[bead,...])

    @staticmethod
    def _frompeaksfcn(args):
        sstrand, alg, refpeaks, bead = args
        try:
            if sstrand:
                refpeaks = SingleStrandProcessor.apply(refpeaks[...], **sstrand.config())
            return (bead, alg.frompeaks(refpeaks[bead]))
        except DataCleaningException:
            return None, None

    def _setupref(self):
        reftask = cast(FitToReferenceTask, deepcopy(self._reftask))
        beads   = set(self._base()[1]['bead'])
        beads  &= set(self._items[self._reference].peaks.keys())
        beads  -= set(self._reftask.fitdata)

        data    = dict(reftask.fitdata)

        sstrand = (Tasks.singlestrand() if self._singlestrand in (True, None) else
                   None                 if not self._singlestrand             else
                   self._singlestrand)

        ref     = self._items[self._reference].peaks
        if len(beads) > 2:
            with ProcessPoolExecutor() as pool:
                lst  = [(sstrand, reftask.fitalg, ref, i) for i in beads]
                data.update({i: j for i, j in pool.map(self._frompeaksfcn, lst)
                             if j is not None})
        else:
            for bead in beads:
                self._frompeaksfcn((sstrand, reftask.fitalg, ref, bead))

        reftask.fitdata = data
        return reftask

    def dataframe(self, *tasks, transform = None, assign = None, **kwa):
        """
        Concatenates all dataframes obtained through *track.peaks.dataframe*
        with the added bonus that a FitToReferenceTask is added automatically
        if the attribute *reference* was set.

        See documentation in *track.peaks.dataframe* for other options
        """
        if self._reference is not None:
            tasks = (self._setupref(),) + tasks

        kwa.update(transform = transform, assign = assign)
        return PeaksTracksDictOperator(self).dataframe(*tasks, **kwa)

    def getmethod(self):
        "Returns the method used by the dynamic map"
        return (_ManualRef(self).run if self._format is None and self._fit else
                _2DRef    (self).run if self._format == '2d'               else
                super().getmethod())

    def getredim(self):
        "Returns the method used by the dynamic map"
        redim   = super().getredim()
        if isinstance(redim, dict):
            redim = list(redim.items())

        if self._format == '2d':
            redim = [i for i in redim if i[0] != 'key']

        if self._format is None and self._fit:
            rngs   = Tasks.getconfig().fittoreferencerange # type: ignore
            redim += [(i, slice(*rngs[i])) for i in ('stretch', 'bias')]
        return redim

class _2DRef(PeaksTracksDictDisplay):
    """Converts 1D graphs to a 2D display"""
    def __init__(self, itms, **kwa):
        super().__init__(itms, **kwa)
        if isinstance(itms, PeaksTracksDictDisplay):
            self.__fcn: Callable = _PTDDisplay.getmethod(itms)

    def run(self, bead):
        "Creates the display"
        plot  = self.__fcn(bead) if np.isscalar(bead) else bead
        crvs  = [(i[1], j) for i, j in plot.data.items() if i[0] == 'Curve'][::2]
        quad  = self.__quadmesh(crvs)
        text  = self.__quadmeshtext(crvs)

        sp1 = [j.data[:,0] for i, j in plot.data.items() if i[0] == 'Scatter'][1::2]
        sp2 = [(np.ones((len(j),3))*(i+.5)+[-.5,.5, np.NaN]).ravel()
               for i, j in enumerate(sp1)]

        if self._reference is not None:
            ref = self.__quadmeshref(sp1, sp2)

        if len(sp1):
            pks = hv.Curve((np.repeat(np.concatenate(sp1), 3), np.concatenate(sp2)),
                           label = 'peaks')(style = self._peakstyle)
        else:
            pks = hv.Curve(([], []), label = 'peaks')(style = self._peakstyle)
        if self._reference is not None:
            return (quad*ref*pks*text).redim(x = 'z', y = 'key', z ='events')
        return (quad*pks*text).redim(x = 'z', y = 'key', z ='events')

    def __quadmesh(self, crvs):
        axis  = crvs[0][1].data[:,0]
        def _inte(other):
            if other.data[:,0].size == 0:
                return np.zeros(axis.size, dtype = 'f4')
            return interp1d(other.data[:,0], other.data[:,1],
                            fill_value = 0.,
                            bounds_error = False,
                            assume_sorted = True)(axis)

        normed = np.concatenate([_inte(j) for i, j in crvs]).reshape(-1, axis.size)
        if self._loglog:
            normed = np.log(normed+1.)
        style  = dict(yaxis = None, logz  = self._logz)
        return hv.QuadMesh((np.append(axis, axis[-1]+axis[1]-axis[0]),
                            np.arange(normed.shape[0]+1),
                            normed))(style = style)

    def __quadmeshtext(self, crvs):
        color = self._textcolor
        return hv.Overlay([hv.Text(0.01, i+.5, j)(style = dict(text_color=color))
                           for i, (j, _) in enumerate(crvs)])

    def __quadmeshref(self, sp1, sp2):
        ind  = 0
        sp2.pop(ind)
        ref2 = (np.zeros((len(sp1[ind]),3))+[0., len(sp1), np.NaN]).ravel()
        ref  = hv.Curve((np.repeat(sp1.pop(ind), 3), ref2), label = f'{self._reference}')
        return ref(style = self._refstyle)

class _ManualRef(PeaksTracksDictDisplay):
    """creates a DynamicMap with a reference to fit dynamically"""
    def __init__(self, itms, **kwa):
        super().__init__(itms, **kwa)
        if isinstance(itms, PeaksTracksDictDisplay):
            self.__fcn: Callable = itms(fit     = False,
                                        reftask = None,
                                        zero    = False).getmethod()
            self.__cache         = [None, ()]

    def run(self, key, bead, stretch, bias):
        "Creates the display"
        cache = self.__cache
        if (key, bead) != cache[0]:
            cache[0] = key, bead
            cache[1] = list(self.__fcn(key, bead))

        mid    = len(cache[1])//2
        clones = [self.__clone(i, stretch, bias) for i in cache[1][mid:]]
        return hv.Overlay(cache[1][:mid]+clones)

    @staticmethod
    def __clone(itm, stretch, bias):
        if isinstance(itm, hv.Text):
            return itm.clone(x = (itm.data[0]-bias)*stretch)
        data = np.copy(itm.data)
        data[:,0] = (data[:,0]-bias)*stretch
        return itm.clone(data = data)

# pylint: disable=bad-continuation
TracksDict.__doc__ = TracksDict.__doc__.replace("""
    * `tracks.peaks` displays peaks per bead and track.""",
    """
    * `tracks.peaks` allows displaying peaks per bead and track. A number of
    keywords are available such as `reference` for aligning all tracks versus a
    reference track, or `fit` for adding stretch and bias sliders. Please check
    the documentation in `tracks.peaks`. For a quick start, the main
    possibilities are:

        * `track.peaks(format = '2d') displays all tracks for a given bead on a
        2D histogram.
        * `track.peaks(format = '1d') displays all tracks for a given bead on a
        1D histogram.
        * `track.peaks(format = None) displays peaks per track and bead individually.
    """)

__all__: List[str] = []
