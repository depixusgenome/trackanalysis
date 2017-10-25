#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating PeaksDict for oligo mapping purposes"
import sys
from   typing                   import List, Type, Sequence, Tuple, cast
from   scipy.interpolate        import interp1d
import numpy                    as np
from   utils                    import DefaultValue
from   scripting.holoviewing    import addto
import sequences
from   peakfinding.processor    import PeaksDict
from   ..processor              import BeadsByHairpinProcessor
from   ..toreference            import ChiSquareHistogramFit

def _get(name, val = None):
    mod = sys.modules[name]
    return mod if val is None else getattr(mod, val)

hv               = _get('holoviews')                             # pylint: disable=invalid-name
_peakfinding     = _get('peakfinding.__scripting__.holoviewing') # pylint: disable=invalid-name
Tasks:      Type = _get('model.__scripting__', 'Tasks')
TracksDict: Type = _get('data.__scripting__', 'TracksDict')

class OligoMappingDisplay(_peakfinding.PeaksDisplay): # type: ignore
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
    def __init__(self, items, **opts):
        super().__init__(items, **opts)
        self._sequence = self._opts.pop('sequence', None)
        self._oligos   = self._opts.pop('oligos',   None)
        self._fit      = self._opts.pop('fit', DefaultValue)
        if 'bias' in self._opts or None not in (self._sequence, self._oligos):
            self._opts['zero'] = False

    def hpins(self):
        "returns haipin positions"
        opts = dict(self._opts)
        opts.pop('stretch', None)
        opts.pop('bias',    None)
        opts.setdefault('kdims', ['z'])
        opts.setdefault('vdims', ['events'])
        style = opts.pop('sequencestyle', dict(color = 'gray'))
        pks   = {}
        if self._labels is not False:
            opts['label'] = 'sequence'

        tmp = sequences.peaks(self._sequence, self._oligos)
        if isinstance(tmp, np.ndarray):
            tmp = (('hairpin 1', tmp),)

        for key, vals in cast(Sequence[Tuple[str, np.ndarray]], tmp):
            xvals = np.repeat(vals['position'], 3)
            yvals = np.concatenate([[(0., .1)[plus], (.9, 1.)[plus], np.NaN]
                                    for plus in vals['orientation']])
            pks[key] = hv.Curve((xvals, yvals), **opts)(style = style)
        return pks

    def fitmap(self):
        "creates a DynamicMap with fitted oligos"
        pins = self.hpins()
        task = Tasks.beadsbyhairpin.get(sequence = self._sequence,
                                        oligos   = self._oligos,
                                        fit      = self._fit)
        info = {i: [(k.key, k.distance) for k in j.beads]
                for i, j in BeadsByHairpinProcessor.apply(self._items, **task.config())}

        def _fcn(bead):
            for key, other in info.items():
                dist = next((j for i, j in other if i == bead), None)
                if dist is None:
                    continue

                crv = self.elements(self._items[[bead]], self._labels, **self._opts,
                                    stretch = dist.stretch,
                                    bias    = dist.bias,
                                    group   = key)
                hpc  = pins[key]
                data = np.copy(hpc.data)
                data[:,1] *= np.nanmax(next(iter(crv)).data[:,1])

                pos  = lambda x: .8*np.nanmax(x)+.2*np.nanmin(x)
                if dist.bias < 0:
                    txt  = f'y = {dist.stretch:.1f} (x  + {np.abs(dist.bias) : .4f})'
                else:
                    txt  = f'y = {dist.stretch:.1f} (x  - {dist.bias : .4f})'
                text = hv.Text(pos(data[:,0]), pos(data[:,1]), txt)
                return hv.Overlay(crv+[hpc.clone(data = data), text], group = key)

        return _fcn

    def hpinmap(self):
        "creates a DynamicMap with oligos to fit"
        opts = dict(self._opts)
        opts.pop('stretch', None)
        opts.pop('bias',    None)
        pins   = self.hpins()
        def _clone(itm, stretch, bias):
            data = np.copy(itm.data)
            data[:,0] = (data[:,0]-bias)*stretch
            return itm.clone(data = data)

        # pylint: disable=dangerous-default-value
        def _over(bead, sequence, stretch, bias, cache = [None, (), None, ()]):
            if bead != cache[0]:
                cache[0] = bead
                cache[1] = self.elements(self._items[[bead]], self._labels, **opts)
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
        beads = super().getredim()
        if None not in (self._sequence, self._oligos) and self._fit is True:
            params = {i: [self._opts[i]] for i in ('stretch', 'bias') if i in self._opts}
            rngs   = Tasks.getconfig().fittohairpin.range.getitems(...)

            pins   = sequences.peaks(self._sequence, self._oligos)
            if isinstance(pins, np.ndarray):
                pins = {'hairpin 1': None}

            return dict(values = dict(bead = beads, sequence = list(dict(pins).keys()), **params),
                        range  = dict(**{i: j for i, j in rngs.items() if i not in params}))
        return beads

@addto(PeaksDict)  # type: ignore
def display(self): # pylint: disable=function-redefined
    "displays peaks"
    return OligoMappingDisplay(self)

class PeaksTracksDictDisplay(_peakfinding.PeaksTracksDictDisplay): # type: ignore
    "tracksdict display for peaks"
    @classmethod
    def _doref(cls, specs, ovrs, ind):
        if None in (specs['reference'], specs['distance']):
            return ovrs

        dist = specs['distance']
        def _peaks(crvs):
            good  = tuple(crvs)[-1]
            crv   = good.data[:,0] if isinstance(good.data, np.ndarray) else good.data[0]
            xvals = (crv[1::3]+crv[::3])*.5
            yvals = (crv[1::3]-crv[::3])*.5
            return dist.frompeaks(np.vstack([xvals, yvals]).T)

        ref  = _peaks(ovrs[ind])
        for i, j in enumerate(ovrs):
            if i == ind:
                continue
            stretch, bias = dist.optimize(ref, _peaks(j))[1:]
            for itm in j:
                itm.data[:,0] = (itm.data[:,0] - bias)*stretch
        return cls._toarea(specs, ovrs, ind)

    @classmethod
    def _same(cls, specs, ref, other):
        return cls._doref(specs, super()._same(specs, ref, other), 0)

    @classmethod
    def _all(cls, specs, fcn, key):
        return cls._doref(specs, super()._all(specs, fcn, key), cls._refindex(specs))

    @classmethod
    def _specs(cls):
        return (super()._specs()
                + (('distance', ChiSquareHistogramFit()),
                   ('peakcolor', 'blue'), ('peakdash', 'dotted'),
                   ('refcolor',  'gray'), ('refdash',  'dotted'),
                   ('logz',      True),   ('loglog',    True),
                   ('textcolor', 'white')))

    @classmethod
    def _to2d(cls, plot, reference, **kwa):
        "converts 1d histograms to 2D"
        crvs  = [(i[1], j) for i, j in plot.data.items() if i[0] == 'Curve'][::2]
        quad  = cls.__quadmesh(crvs, kwa)
        text  = cls.__quadmeshtext(crvs, kwa)

        sp1 = [j.data[:,0] for i, j in plot.data.items() if i[0] == 'Scatter'][1::2]
        sp2 = [(np.ones((len(j),3))*(i+.5)+[-.5,.5, np.NaN]).ravel()
               for i, j in enumerate(sp1)]

        if reference is not None:
            ref = cls.__quadmeshref(sp1, sp2, reference, kwa)

        pks = hv.Curve((np.repeat(np.concatenate(sp1), 3), np.concatenate(sp2)),
                       label = 'peaks')
        pks = pks(style = dict(color     = kwa.get('peakcolor', 'blue'),
                               line_dash = kwa.get('peakdash', 'dotted')))
        if reference is not None:
            return (quad*ref*pks*text).redim(x = 'z', y = 'key', z ='events')
        return (quad*pks*text).redim(x = 'z', y = 'key', z ='events')

    @staticmethod
    def __quadmesh(crvs, kwa):
        axis  = crvs[0][1].data[:,0]
        inte  = lambda i: interp1d(i.data[:,0], i.data[:,1],
                                   fill_value = 0.,
                                   bounds_error = False,
                                   assume_sorted = True)(axis)

        normed = np.concatenate([inte(j) for i, j in crvs]).reshape(-1, axis.size)
        if kwa.get('loglog', False):
            normed = np.log(normed+1.)
        style  = dict(yaxis = None, logz  = kwa.get('logz', True))
        return hv.QuadMesh((np.append(axis, axis[-1]+axis[1]-axis[0]),
                            np.arange(normed.shape[0]+1),
                            normed))(style = style)

    @staticmethod
    def __quadmeshtext(crvs, kwa):
        color = kwa.get('textcolor', 'white')
        return hv.Overlay([hv.Text(0., i+.5, j)(style = dict(text_color=color))
                           for i, (j, _) in enumerate(crvs)])

    @staticmethod
    def __quadmeshref(sp1, sp2, reference, kwa):
        ind  = 0
        sp2.pop(ind)
        ref2 = (np.zeros((len(sp1[ind]),3))+[0., len(sp1), np.NaN]).ravel()
        ref  = hv.Curve((np.repeat(sp1.pop(ind), 3), ref2), label = reference)
        return ref(style = dict(color = kwa.get('refcolor', 'gray'),
                                line_dash = kwa.get('refdash', 'dotted')))

    def displaybead(self, reference = None, **kwa):
        """
        For a given track, all beads are overlayed.

        Keywords are:

        * *reference*: the reference is displayed as an area
        * *distance*: a *HistogramFit* object (default) or *None*. This
        objects computes a stretch and bias which is applied to the x-axis of
        non-reference items.
        """
        return self.display('bead', reference, **kwa)

    def display1d(self, reference = None, **kwa):
        """
        For a given bead, all tracks are overlayed.

        Keywords are:

        * *reference*: the reference is displayed as an area,
        * *distance*: a *HistogramFit* object (default) or *None*. This objects
        computes a stretch and bias which is applied to the x-axis of
        non-reference items.
        """
        return self.display('1d', reference, **kwa)

    def display2d(self, reference = None, **kwa):
        """
        For a given bead, all tracks are shown on a 2D histogram.

        Keywords are:

        * *reference*: the reference is displayed as an area,
        * *distance*: a *HistogramFit* object (default) or *None*. This objects
        computes a stretch and bias which is applied to the x-axis of
        non-reference items.
        """
        return self.display('2d', reference, **kwa)

    def displayonebyone(self, reference = None, **kwa):
        """
        Keywords are:


        * *reference*: the reference is removed from the *key* widget and
        allways displayed to the left independently.
        * *refdims*: if set to *True*, the reference gets its own dimensions.
        Thus zooming and spanning is independant.
        * *reflayout*: can be set to 'top', 'bottom', 'left' or 'right'
        """
        return self.display(None, reference, **kwa)

    def display(self, overlay = '2d', reference = None, **kwa):
        """
        A hv.DynamicMap showing peaks

        Options are:

            * *overlay* == '1d': for a given bead, all tracks are overlayed,
            see 'display1d'.

            * *overlay* == '2d': for a given bead, all tracks are shown on a 2D
            histogram, see 'display2d'.

            * *overlay* == 'bead': for a given track, all beads are overlayed,
            see 'displaybead'.


            * *overlay* == None: see 'displayonebyone'.
        """

        kwa.setdefault('reflayout', 'same' if overlay is None else 'bottom')
        kwa.setdefault('refdims', False)
        if self.beads:
            kwa.setdefault('bead', self.beads)
        if self.keys:
            kwa.setdefault('key', self.keys)

        if overlay is not None:
            overlay = overlay.lower()
            is2d    = overlay == '2d'
            overlay = 'key' if overlay in ("1d", "2d") else overlay
        else:
            is2d    = False

        if is2d:
            beads = kwa['bead'] if 'bead' in kwa else self.tracks.beads(*kwa.get('key', ()))

        dmap    = self.run(self.tracks, 'peaks', overlay, reference, dict(kwa))
        if is2d:
            fcn = lambda bead: self._to2d(dmap[bead], reference, **kwa)
            return hv.DynamicMap(fcn, kdims = ['bead']).redim.values(bead = beads)
        return dmap

@addto(TracksDict) # type: ignore
@property
def peaks(self):
    "A hv.DynamicMap showing peaks"
    return PeaksTracksDictDisplay(self)

__all__: List[str] = []
