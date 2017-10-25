#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating PeaksDict for scripting purposes"
from   typing                import List, Iterator, Type
from   functools             import partial
from   copy                  import deepcopy
import sys
import numpy            as     np
from   scripting.holoviewing import addto
from   ..probabilities       import Probability
from   ..processor           import PeaksDict
from   .                     import Detailed

def _get(name, attr = None):
    mod = sys.modules[name]
    return mod if attr is None else getattr(mod, attr)

# pylint: disable=invalid-name
hv                      = _get('holoviews')
TracksDict:        Type = _get('data.__scripting__', 'TracksDict')
CycleDisplay:      Type = _get('data.__scripting__.holoviewing.display',
                               'CycleDisplay')
TracksDictDisplay: Type = _get('data.__scripting__.holoviewing.tracksdict',
                               'TracksDictDisplay')

class PeaksDisplay(CycleDisplay): # type: ignore
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
    # pylint: disable=too-many-arguments,arguments-differ
    @staticmethod
    def __histogram(det, params, norm, opts, estyle):
        return hv.Curve((det.xaxis(*params), det.yaxis(norm)), **opts)(style = estyle)

    @staticmethod
    def __events(det, params, opts, estyle, hist):
        if len(det.positions) == 0:
            return hv.Scatter(([], []), **opts)(style = estyle)

        pks   = (np.concatenate(det.positions)-params[1])*params[0]
        yvals = [hist[i] for i in pks]
        return hv.Scatter((pks, yvals), **opts)(style = estyle)

    @classmethod
    def __errorbars(cls, det, params, opts, pstyle, hist):
        if len(det.positions) == 0:
            return hv.Curve(([], []), **opts)(style = pstyle)

        means = [((i-params[1])*params[0], Probability.resolution(j))
                 for i, j in det.output]
        xvals = np.hstack([[i-j, i+j, np.NaN]         for i, j in means])
        yvals = np.hstack([[hist[i], hist[i], np.NaN] for i, j in means])
        return hv.Curve((xvals, yvals), **opts)(style = pstyle)

    @staticmethod
    def __peaks(det, params, opts, pstyle, hist):
        if len(det.positions) == 0:
            return hv.Scatter(([], []), **opts)(style = pstyle)

        means = [(i-params[1])*params[0] for i, _ in det.output]
        yvals = [hist[i] for i in means]
        return hv.Scatter((means, yvals), **opts)(style = pstyle)

    @staticmethod
    def graphdims():
        "returns the dimension names"
        return {'kdims': ['z'], 'vdims': ['events']}

    def elements(self, evts, **opts):
        "shows overlayed Curve items"
        cnf  = {i: deepcopy(j) for i, j in self._opts.items()
                if i not in ('bias', 'stretch')}
        cnf.update(opts)
        prec = opts.pop('precision', None)
        try:
            return self.detailed(evts.detailed(..., prec), **cnf)
        except Exception as exc: # pylint: disable=broad-except
            return self.errormessage(exc)

    def detailed(self, dets, **opts):
        "shows overlayed Curve items"
        opts.pop('sequencestyle', None)
        for i, j in self.graphdims().items():
            opts.setdefault(i, j)

        never  = opts.pop('neverempty', False)
        pstyle = dict(opts.pop('peakstyle',  dict(size = 5, color = 'green')))
        estyle = dict(opts.pop('eventstyle', dict(size = 3)))

        params = opts.pop('stretch', 1.), opts.pop('bias', 0.)
        norm   = opts.pop('norm', 'events')

        if not isinstance(dets, Iterator):
            dets = (dets,)

        itms = []
        def _do(det):
            if opts.pop('zero', True):
                cparams = params[0], params[1]+det.zero
            else:
                cparams = params

            if isinstance(self._labels, str):
                opts['label'] = self._labels
            elif self._labels is True:
                opts['label'] = 'histogram'
            itms.append(self.__histogram(det, cparams, norm, opts, estyle))
            itms.append(self.__events   (det, cparams, opts, estyle, itms[-1]))

            if isinstance(self._labels, str):
                opts.pop('label')
            elif self._labels is True:
                opts['label'] = 'peaks'

            itms.append(self.__peaks    (det, cparams, opts, pstyle, itms[-2]))
            itms.append(self.__errorbars(det, cparams, opts, pstyle, itms[-3]))
        for det in dets:
            _do(det)
        if len(itms) == 0 and never:
            _do(Detailed(None, None))
        return itms

    def _run(self, evts, **opts):
        "shows overlayed Curve items"
        return hv.Overlay(self.elements(evts, **opts))

    def _perbead(self, bead, **opts):
        return self._run(self._items[[bead]], **opts)

    def _perall(self, **opts):
        return self._run(self._items, **opts)

    def getmethod(self):
        "Returns the method used by the dynamic map"
        return getattr(self, '_per'+str(self._kdim), self._perall)

    def getredim(self):
        "Returns the keys used by the dynamic map"
        if self._kdim == 'bead':
            return ((self._kdim, list(set([i for i in self._items.keys()
                                           if self._items.isbead(i)]))),)
        return None

class DetailedDisplay(PeaksDisplay): # type: ignore
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
    def getredim(self):
        "Returns the method used by the dynamic map"
        return None

    def getmethod(self):
        "Returns the method used by the dynamic map"
        return self._perall

    def _perall(self, **opts):
        "Returns the method used by the dynamic map"
        return self.detailed(self._items, **opts)

    display = _perall

@addto(Detailed)  # type: ignore
@property
def display(self): # pylint: disable=function-redefined
    "Displays peaks."
    return DetailedDisplay(self)

@addto(PeaksDict)  # type: ignore
@property
def display(self): # pylint: disable=function-redefined
    "displays peaks"
    return PeaksDisplay(self)

@addto(PeaksDict)
def map(self, fcn, **kwa): # pylint: disable=redefined-builtin
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    kwa.setdefault('bead', list(i for i in self.keys()))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

class PeaksTracksDictDisplay(TracksDictDisplay): # type: ignore
    "tracksdict display for peaks"
    def __init__(self, dico, **opts):
        opts['name'] = 'peaks'
        super().__init__(dico, **opts)

    @staticmethod
    def _specs(_):
        return ('refdims',  True), ('reflayout', 'bottom')

    @staticmethod
    def _refindex(specs):
        if specs.get('reference', None) is None:
            return None
        return specs['kdims'][specs['overlay']].index(specs['reference'])

    @classmethod
    def _toarea(cls, specs, ovrs, ind):
        if specs.get('reference', None) is not None:
            area = next(iter(ovrs[ind])).to(hv.Area)
            ovrs[ind] = hv.Overlay([area(style = dict(alpha = 0.5))] + list(ovrs[ind]),
                                   label = ovrs[ind].label,
                                   group = ovrs[ind].group)
        return ovrs

    @classmethod
    def _all(cls, specs, fcn, key, **opts):
        return cls._toarea(specs,
                           super()._all(specs, fcn, key, **opts),
                           cls._refindex(specs))


@addto(TracksDict) # type: ignore
@property
def peaks(self):
    "A hv.DynamicMap showing peaks"
    return PeaksTracksDictDisplay(self)

__all__: List[str] = []
