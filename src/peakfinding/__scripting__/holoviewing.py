#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating PeaksDict for scripting purposes"
from   typing           import List, Iterator, Type
from   functools        import partial
import sys
import numpy            as np
from   utils.decoration import addto
from   ..processor      import PeaksDict
from   .                import Detailed

def _get(name, attr = None):
    mod = sys.modules[name]
    return mod if attr is None else getattr(mod, attr)

# pylint: disable=invalid-name
hv               = _get('holoviews')
TracksDict: Type = _get('data.__scripting__', 'TracksDict')
Display:    Type = _get('data.__scripting__.holoviewing', 'Display')
TracksDictDisplay: Type = _get('data.__scripting__.holoviewing.tracksdict',
                               'TracksDictDisplay')

class PeaksDisplay(Display): # type: ignore
    "displays peaks"
    # pylint: disable=too-many-arguments,arguments-differ
    @staticmethod
    def __histogram(det, params, norm, opts, estyle):
        xvals = det.xaxis(*params)
        yvals = det.yaxis(norm)
        return hv.Curve((xvals, yvals), **opts)(style = estyle)

    @staticmethod
    def __events(det, params, opts, estyle, hist):
        pks   = (np.concatenate(det.positions)-params[1])*params[0]
        yvals = [hist[i] for i in pks]
        return hv.Scatter((pks, yvals), **opts)(style = estyle)

    @staticmethod
    def __errors(arr):
        good = [np.nanmean(i[1] if isinstance(i, tuple) else np.concatenate(i['data']))
                for i in arr if i is not None]
        return 0. if len(good) == 1 else np.std(good)

    @classmethod
    def __errorbars(cls, det, params, opts, pstyle, hist):
        means = [((i-params[1])*params[0], cls.__errors(j)) for i, j in det.output]
        xvals = sum(([i-j, i+j, np.NaN] for i, j in means), [])
        yvals = sum(([hist[i], hist[i], np.NaN] for i, j in means), [])
        return hv.Curve((xvals, yvals), **opts)(style = pstyle)

    @staticmethod
    def __peaks(det, params, opts, pstyle, hist):
        means = [(i-params[1])*params[0] for i, _ in det.output]
        yvals = [hist[i] for i in means]
        return hv.Scatter((means, yvals), **opts)(style = pstyle)

    @classmethod
    def elements(cls, evts, labels, **opts):
        "shows overlayed Curve items"
        prec = opts.pop('precision', None)
        try:
            return cls.detailed(evts.detailed(..., prec), labels, **opts)
        except Exception as exc: # pylint: disable=broad-except
            return cls.errormessage(exc,
                                    x = opts.get('kdims', ['z'])[0],
                                    y = opts.get('vdims', ['events'])[0])

    @classmethod
    def detailed(cls, dets, labels, **opts):
        "shows overlayed Curve items"
        opts.pop('sequencestyle', None)

        opts.setdefault('kdims', ['z'])
        opts.setdefault('vdims', ['events'])

        pstyle = dict(opts.pop('peakstyle',  dict(size = 5, color = 'green')))
        estyle = dict(opts.pop('eventstyle', dict(size = 3)))

        params = opts.pop('stretch', 1.), opts.pop('bias', 0.)
        norm   = opts.pop('norm', 'events')

        if not isinstance(dets, Iterator):
            dets = (dets,)

        itms = []
        for det in dets:
            if opts.pop('zero', True):
                cparams = params[0], params[1]+det.zero
            else:
                cparams = params

            if isinstance(labels, str):
                opts['label'] = labels
            elif labels is True:
                opts['label'] = 'histogram'
            itms.append(cls.__histogram(det, cparams, norm, opts, estyle))
            itms.append(cls.__events   (det, cparams, opts, estyle, itms[-1]))

            if isinstance(labels, str):
                opts.pop('label')
            elif labels is True:
                opts['label'] = 'peaks'

            itms.append(cls.__peaks    (det, cparams, opts, pstyle, itms[-2]))
            itms.append(cls.__errorbars(det, cparams, opts, pstyle, itms[-3]))
        return itms

    @classmethod
    def run(cls, evts, labels, **opts):
        "shows overlayed Curve items"
        return hv.Overlay(cls.elements(evts, labels, **opts))

@addto(Detailed)  # type: ignore
def display(self, # pylint: disable=function-redefined,too-many-arguments
            labels = None, **opts):
    """
    Displays peaks.

    Arguments are:

        * *labels*: if *False*, no labels are added. If *None*, labels are added
        if 3 or less beads are shown.
        * *stretch* and *bias* values can be provided manually
        * *zero* set to *True* will set the x-axis zero to the first peak position.
        * *eventstyle*, *peakstyle* can be used to set the style
        of corresponding graph elements.
    """
    return PeaksDisplay.detailed(self, labels, **opts)

@addto(PeaksDict)  # type: ignore
def display(self, # pylint: disable=function-redefined,too-many-arguments
            kdim     = 'bead',
            labels   = None,
            **opts):
    """
    Displays peaks.

    Arguments are:

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
    disp = PeaksDisplay
    if kdim == 'bead':
        beads = list(set([i for i in self.keys() if self.isbead(i)]))
        def _fcn(bead):
            return disp.run(self[[bead]], labels, **opts)
        return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)
    return disp.run(self, labels, **opts)

@addto(PeaksDict)
def map(self, fcn, **kwa): # pylint: disable=redefined-builtin
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    kwa.setdefault('bead', list(i for i in self.keys()))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

class PeaksTracksDictDisplay(TracksDictDisplay): # type: ignore
    "tracksdict display for peaks"
    @staticmethod
    def _refindex(specs):
        return specs['kdims'][specs['overlay']].index(specs['reference'])

    @classmethod
    def _toarea(cls, specs, ovrs):
        if specs['reference'] is not None:
            ind  = cls._refindex(specs)
            area = next(iter(ovrs[ind])).to(hv.Area)
            ovrs[ind] = hv.Overlay([area(style = dict(alpha = 0.5))] + list(ovrs[ind]),
                                   label = ovrs[ind].label,
                                   group = ovrs[ind].group)
        return ovrs

    @classmethod
    def _all(cls, specs, fcn, key):
        return cls._toarea(specs, super()._all(specs, fcn, key))

@addto(TracksDict) # type: ignore
def peaks(self, overlay = 'key', reference = None, **kwa):
    """
    A hv.DynamicMap showing peaks

    Options are:

        * *overlay* == 'key': for a given bead, all tracks are overlayed
        The *reference* option can be used to indicate the top-most track.
        * *overlay* == 'bead': for a given track, all beads are overlayed
        The *reference* option can be used to indicate the top-most bead.
        * *overlay* == None:

            * *reference*: the reference is removed from the *key* widget and
            allways displayed to the left independently.
            * *refdims*: if set to *True*, the reference gets its own dimensions.
            Thus zooming and spanning is independant.
            * *reflayout*: can be set to 'top', 'bottom', 'left' or 'right'
    """
    kwa.setdefault('reflayout', 'bottom')
    return PeaksTracksDictDisplay.run(self, 'peaks', overlay, reference, kwa)

__all__: List[str] = []
