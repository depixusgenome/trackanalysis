#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating PeaksDict for oligo mapping purposes"
import sys
from   typing                   import (List, Type, # pylint: disable=unused-import
                                        Sequence, Tuple, cast, Dict, Optional)
from   copy                     import deepcopy
from   scipy.interpolate        import interp1d
import numpy                    as np

import sequences

from   utils                    import DefaultValue
from   peakfinding.processor    import PeaksDict    # pylint: disable=unused-import

from   ..processor.fittohairpin import (BEADKEY,    # pylint: disable=unused-import
                                        FitToHairpinDict, Distance)
from   ..toreference            import ChiSquareHistogramFit

def _get(name, val = None):
    mod = sys.modules[name]
    return mod if val is None else getattr(mod, val)

hv               = _get('holoviews')                              # pylint: disable=invalid-name
hvpeakfinding    = _get('peakfinding.__scripting__.holoviewing')  # pylint: disable=invalid-name
Tasks:      Type = _get('model.__scripting__', 'Tasks')
TracksDict: Type = _get('data.__scripting__', 'TracksDict')

class OligoMappingDisplay(hvpeakfinding.PeaksDisplay, display = PeaksDict): # type: ignore
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
    _zero          = True
    _sequence      = None
    _oligos        = None
    _fit           = DefaultValue
    _sequencestyle = dict(color = 'gray')
    KEYWORDS       = hvpeakfinding.PeaksDisplay.KEYWORDS | frozenset(locals())
    def __init__(self, items, **opts):
        super().__init__(items, **opts)
        if self._bias is not None or None not in (self._sequence, self._oligos):
            self._zero = False

    def hpins(self):
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

    def fitmap(self):
        "creates a DynamicMap with fitted oligos"
        pins  = self.hpins()
        fits  = self._items.new(FitToHairpinDict,
                                config   = dict(sequence = self._sequence,
                                                oligos   = self._oligos,
                                                fit      = self._fit))

        cache = {} # type: Dict[BEADKEY, Tuple[str, Distance]]
        def _fcn(bead):
            if bead not in cache:
                cache[bead] = min(fits[bead].distances.items(), key = lambda i: i[1][0])
            key, dist = cache[bead]

            tmp = self(stretch = dist.stretch, bias = dist.bias)
            crv = tmp.elements(self._items[[bead]], group = key)

            hpc  = pins[key]
            data = np.copy(hpc.data)
            data[:,1] *= np.nanmax(next(iter(crv)).data[:,1])

            pos  = lambda x: .8*np.nanmax(x)+.2*np.nanmin(x)
            if dist.bias < 0:
                txt  = f'y = {dist.stretch:.1f} (x  + {np.abs(dist.bias) : .4f})'
            else:
                txt  = f'y = {dist.stretch:.1f} (x  - {dist.bias : .4f})'
            text = hv.Text(pos(data[:,0]), pos(data[:,1]), txt,
                           kdims = hpc.kdims+hpc.vdims)
            return hv.Overlay(crv+[hpc.clone(data = data), text], group = key)
        return _fcn

    def hpinmap(self):
        "creates a DynamicMap with oligos to fit"
        pins = self.hpins()
        def _clone(itm, stretch, bias):
            data = np.copy(itm.data)
            data[:,0] = (data[:,0]-bias)*stretch
            return itm.clone(data = data)

        # pylint: disable=dangerous-default-value
        def _over(bead, sequence, stretch, bias, cache = [None, (), None, ()]):
            if bead != cache[0]:
                cache[0] = bead
                cache[1] = self.elements(self._items[[bead]])
            clones = [_clone(i, stretch, bias) for i in cache[1]]

            if sequence != cache[2]:
                hpc        = pins[sequence]
                data       = np.copy(hpc.data)
                data[:,1] *= np.nanmax(clones[0].data[:,1])
                cache[2]   = sequence
                cache[3]   = [hpc.clone(data = data)]

            return hv.Overlay(clones+cache[3])

        return _over

    def getmethod(self):
        "Returns the method used by the dynamic map"
        if None not in (self._sequence, self._oligos):
            return self.hpinmap() if self._fit is True else self.fitmap()
        return super().getmethod()

    def getredim(self):
        "Returns the keys used by the dynamic map"
        values = list(super().getredim())
        if None not in (self._sequence, self._oligos) and self._fit is True:
            params = tuple((i, getattr(self, '_'+i)) for i in ('stretch', 'bias')
                           if getattr(self, '_'+i) != getattr(self.__class__, '_'+i))
            rngs   = Tasks.getconfig().fittohairpin.range.getitems(...)

            pins   = sequences.peaks(self._sequence, self._oligos)
            if isinstance(pins, np.ndarray):
                pins = {'hairpin 1': None}

            values.append(('sequence', sorted(dict(pins).keys())))
            values.extend(params)
            values.extend((i, slice(*rngs[i])) for i in ('stretch', 'bias')
                          if i not in (k for k, _ in params))
            return values
        return values

class PeaksTracksDictDisplay(hvpeakfinding.PeaksTracksDictDisplay, # type: ignore
                             peaks = TracksDict):
    """
    A hv.DynamicMap showing peaks

    Attributes are:

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
    _format    = "2d"
    _distance  = ChiSquareHistogramFit()
    _refdims   = False
    _peakcolor = 'blue'
    _peakdash  = 'dotted'
    _refstyle  = dict(color = 'gray', line_dash = 'dotted')
    _logz      = True
    _loglog    = True
    _textcolor = 'white'
    _fit       = False
    KEYWORDS   = hvpeakfinding.PeaksTracksDictDisplay.KEYWORDS | frozenset(locals())
    def __init__(self, items, **opts):
        super().__init__(items, **opts)
        if self._format in ('1d', '2d'):
            self._overlay = 'key'
        elif 'overlay' not in opts:
            self._overlay = None
        if 'reflayout' not in opts:
            self._reflayout = 'same' if self._format is None else 'bottom'
        if self._format == "2d" and 'peakstyle' not in opts:
            self._peakstyle = dict(color = 'blue', line_dash = 'dotted')

    @staticmethod
    def _equations(ovrs, ind, params):
        first = next(iter(tuple(ovrs[ind])))
        kdims = first.kdims + first.vdims
        minv  = [np.nanmin(first.data[:,k]) for k in range(2)]
        maxv  = [np.nanmax(first.data[:,k]) for k in range(2)]

        temp  = f'{{}}: {kdims[1]} = {{:.4f}} · ({kdims[0]} - {{:.4f}})'
        txt   = '\n'.join(temp.format(*i) for i in params)
        if len(params) == 1:
            txt = txt.split(':')[1]

        return hv.Text(minv[0]*.7+maxv[0]*.3, minv[1]*.3+maxv[1]*.7,
                       txt, kdims = kdims)

    def _convert(self, kdims, ovrs):
        ovrs = super()._convert(kdims, ovrs)
        ind  = self._refindex(kdims)
        if (None in (self._reference, self._distance, ind)  or
                ind >= len(ovrs)                            or
                len(tuple(ovrs[ind])) == 0):
            return ovrs

        def _peaks(crvs):
            if len(tuple(crvs)) == 0:
                return

            good  = tuple(crvs)[-1]
            if len(good.data) == 0:
                return

            crv   = good.data[:,0] if isinstance(good.data, np.ndarray) else good.data[0]
            xvals = (crv[1::3]+crv[::3])*.5
            yvals = (crv[1::3]-crv[::3])*.5
            return self._distance.frompeaks(np.vstack([xvals, yvals]).T)

        ref = _peaks(ovrs[ind])
        if ref is None:
            return ovrs

        txt   = [] # type: List[Tuple[str, float, float]]
        for i, j in enumerate(ovrs):
            if i == ind:
                continue

            j = tuple(j)
            if len(j) == 0 or len(j[0].data) == 0:
                continue

            pks  = _peaks(j)
            if pks is not None:
                stretch, bias = self._distance.optimize(ref, pks)[1:]
                for itm in j:
                    itm.data[:,0] = (itm.data[:,0] - bias)*stretch
                label = next((i.label for i in tuple(j) if i.label), None)
                if label:
                    txt.append((label, stretch, bias))

        if len(txt) < 4:
            ovrs = list(ovrs)
            return hv.Overlay(ovrs+[self._equations(ovrs, ind, txt)])

    def _to2d(self, plot):
        "converts 1d histograms to 2D"
        crvs  = [(i[1], j) for i, j in plot.data.items() if i[0] == 'Curve'][::2]
        quad  = self.__quadmesh(crvs)
        text  = self.__quadmeshtext(crvs)

        sp1 = [j.data[:,0] for i, j in plot.data.items() if i[0] == 'Scatter'][1::2]
        sp2 = [(np.ones((len(j),3))*(i+.5)+[-.5,.5, np.NaN]).ravel()
               for i, j in enumerate(sp1)]

        if self._reference is not None:
            ref = self.__quadmeshref(sp1, sp2)

        pks = hv.Curve((np.repeat(np.concatenate(sp1), 3), np.concatenate(sp2)),
                       label = 'peaks')(style = self._peakstyle)
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
        return hv.Overlay([hv.Text(0., i+.5, j)(style = dict(text_color=color))
                           for i, (j, _) in enumerate(crvs)])

    def __quadmeshref(self, sp1, sp2):
        ind  = 0
        sp2.pop(ind)
        ref2 = (np.zeros((len(sp1[ind]),3))+[0., len(sp1), np.NaN]).ravel()
        ref  = hv.Curve((np.repeat(sp1.pop(ind), 3), ref2), label = self._reference)
        return ref(style = self._refstyle)

    def _withfit(self):
        "creates a DynamicMap with a reference to fit"
        def _clone(itm, stretch, bias):
            data = np.copy(itm.data)
            data[:,0] = (data[:,0]-bias)*stretch
            return itm.clone(data = data)

        # pylint: disable=dangerous-default-value
        fcn = self(fit = False, distance = None, zero = False).getmethod()
        def _over(key, bead, stretch, bias, cache = [None, ()]):
            if bead != cache[0]:
                cache[0] = bead
                cache[1] = list(fcn(key, bead))

            mid    = len(cache[1])//2+1
            clones = [_clone(i, stretch, bias) for i in cache[1][mid:]]
            return hv.Overlay(cache[1][:mid]+clones)
        return _over

    def getmethod(self):
        "Returns the method used by the dynamic map"
        if self._format is None and self._fit:
            return self._withfit()

        fcn = super().getmethod()
        if self._format == '2d':
            return lambda bead: self._to2d(fcn(bead))
        return fcn

    def getredim(self):
        "Returns the method used by the dynamic map"
        redim   = super().getredim()
        if isinstance(redim, dict):
            redim = list(redim.items())

        if self._format == '2d':
            redim = [i for i in redim if i[0] != 'key']

        if self._format is None and self._fit:
            rngs   = Tasks.getconfig().fittoreference.range.getitems(...)
            redim += [(i, slice(*rngs[i])) for i in ('stretch', 'bias')]
        return redim

__all__: List[str] = []
