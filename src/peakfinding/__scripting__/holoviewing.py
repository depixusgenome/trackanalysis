#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating PeaksDict for scripting purposes"
from   typing                import List, Union, Iterator, cast
from   functools             import partial
from   copy                  import deepcopy
import numpy                 as     np

from   utils.holoviewing     import addto, displayhook, hv
from   taskmodel.__scripting__   import Tasks
from   data.__scripting__    import TracksDict # pylint: disable=unused-import
from   data.__scripting__.holoviewing.trackviews import CycleDisplay as _CycleDisplay
from   data.__scripting__.holoviewing.tracksdict import TracksDictDisplay
from   ..probabilities        import Probability
from   ..processor            import PeaksDict, SingleStrandProcessor, SingleStrandTask
from   ..processor.projection import PeakProjectorDict
from   .                      import Detailed, PeaksTracksDictOperator

displayhook(PeaksDict)
class PeaksDisplay(_CycleDisplay, display = PeaksDict): # type: ignore
    """
    Displays peaks.

    Attributes are:

    * *kdim*: if 'bead', then a *holoviews.DynamicMap* is returned, displaying
    beads independently.
    * *precision* is the noise level used to find peaks
    * *labels*: if *False*, no labels are added. If *None*, labels are added
    if 3 or less beads are shown.
    * *stretch* and *bias* values can be provided manually
    * *zero* set to *True* will set the x-axis zero to the first peak position.
    * *singlestrand* will remove the single-strand peak unless set to `False`
    """
    _zero                                        = True
    _peakstyle                                   = dict(size = 5, color = 'green')
    _eventstyle                                  = dict(size = 3)
    _norm                                        = 'events'
    _precision                                   = None
    _singlestrand: Union[SingleStrandTask, bool] = None
    KEYWORDS                                     = _CycleDisplay.KEYWORDS | frozenset(locals())

    # pylint: disable=too-many-arguments,arguments-differ
    @staticmethod
    def __histogram(det, params, norm, opts):
        return hv.Curve((det.xaxis(*params), det.yaxis(norm)), **opts)

    @staticmethod
    def __events(det, params, opts, estyle, hist):
        if len(det.positions) == 0:
            return hv.Scatter(([], []), **opts).options(**estyle)

        pks   = (np.concatenate(det.positions)-params[1])*params[0]
        pks   = pks[np.concatenate(det.ids) != np.iinfo('i4').max]
        yvals = [hist[i] for i in pks]
        return hv.Scatter((pks, yvals), **opts).options(**estyle)

    @classmethod
    def __errorbars(cls, det, params, opts, pstyle, hist):
        if 'size' in pstyle:
            pstyle = dict(pstyle)
            pstyle.pop('size')

        if len(det.positions) == 0:
            return hv.Curve(([], []), **opts).options(**pstyle)

        means = [((i-params[1])*params[0], Probability.resolution(j))
                 for i, j in det.output]
        xvals = np.hstack([[i-j, i+j, np.NaN]         for i, j in means])
        yvals = np.hstack([[hist[i], hist[i], np.NaN] for i, j in means])
        return hv.Curve((xvals, yvals), **opts).options(**pstyle)

    @staticmethod
    def __peaks(det, params, opts, pstyle, hist):
        if len(det.positions) == 0:
            return hv.Scatter(([], []), **opts).options(**pstyle)

        means = [(i-params[1])*params[0] for i, _ in det.output]
        yvals = [hist[i] for i in means]
        return hv.Scatter((means, yvals), **opts).options(**pstyle)

    @staticmethod
    def graphdims():
        "returns the dimension names"
        return {'kdims': ['z'], 'vdims': ['events']}

    def elements(self, evts, **opts):
        "shows overlayed Curve items"
        cnf  = deepcopy(self._opts)
        cnf.update(opts)
        try:
            return self.detailed(evts.detailed(..., self._precision), **cnf)
        except Exception as exc: # pylint: disable=broad-except
            return self.errormessage(exc)

    def detailed(self, dets, **opts):
        "shows overlayed Curve items"
        for i, j in self.graphdims().items():
            opts.setdefault(i, j)

        never  = opts.pop('neverempty', False)
        pstyle = self._peakstyle
        estyle = self._eventstyle
        norm   = self._norm
        params = self._stretch, self._bias

        if not isinstance(dets, Iterator):
            dets = (dets,)

        itms = []
        def _do(det):
            cparams = (params[0], params[1]+det.zero) if self._zero else params

            if isinstance(self._labels, str):
                opts['label'] = self._labels
            elif self._labels is True:
                opts['label'] = 'histogram'

            itms.append(self.__histogram(det, cparams, norm, opts))
            itms.append(self.__events   (det, cparams, opts, estyle, itms[-1]))

            if isinstance(self._labels, str):
                opts.pop('label')
            elif self._labels is True:
                opts['label'] = 'peaks'

            itms.append(self.__peaks    (det, cparams, opts, pstyle, itms[-2]))
            itms.append(self.__errorbars(det, cparams, opts, pstyle, itms[-3]))


            if getattr(det, 'params', (1., 0.)) != (1., 0.):
                tmp     = getattr(det, 'params')
                cparams = tmp[0]*cparams[0], tmp[0]*tmp[1]+cparams[1]
            cparams = np.round(cparams, 4)
            if tuple(cparams) != (1., 0.):
                if cparams[1] < 0.:
                    itms[-4].dpx_label = (f'{opts["vdims"][0]} = '
                                          f'{cparams[0]}·({opts["kdims"][0]}+{-cparams[1]})')
                else:
                    itms[-4].dpx_label = (f'{opts["vdims"][0]} = '
                                          f'{cparams[0]}·({opts["kdims"][0]}-{cparams[1]})')

        dets = tuple(dets)
        for det in dets:
            _do(det)
        if len(itms) == 0 and never:
            _do(Detailed(None, None))
        return itms

    @property
    def _ssitems(self):
        if self._singlestrand:
            sstrand = (Tasks.singlestrand() if self._singlestrand is True else
                       self._singlestrand)
            return SingleStrandProcessor.apply(self._items[...], **sstrand.config())
        return self._items

    def _run(self, evts, **opts):
        "shows overlayed Curve items"
        return hv.Overlay(self.elements(evts, **opts))

    def _perbead(self, bead, **opts):
        return self._run(self._ssitems[[bead]], **opts)

    def _perall(self, **opts):
        return self._run(self._ssitems, **opts)

    def getmethod(self):
        "Returns the method used by the dynamic map"
        return getattr(self, '_per'+str(self._kdim), self._perall)

    def getredim(self):
        "Returns the keys used by the dynamic map"
        if self._kdim == 'bead':
            return ((self._kdim, list({i for i in self._items.keys()
                                       if self._items.isbead(i)})),)
        return None

displayhook(PeakProjectorDict)
class PeakProjectorDictDisplay(PeaksDisplay, display = PeakProjectorDict): # type: ignore
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

displayhook(Detailed)
class DetailedDisplay(PeaksDisplay, display = Detailed): # type: ignore
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
        return hv.Overlay(self.detailed(self._items, **opts))

    display = _perall

@addto(PeaksDict)
def map(self, fcn, **kwa): # pylint: disable=redefined-builtin
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    kwa.setdefault('bead', list(i for i in self.keys()))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

class PeaksTracksDictDisplay(TracksDictDisplay, peaks = TracksDict): # type: ignore
    "tracksdict display for peaks"
    _overlay    = 'key'
    _reflayout  = 'bottom'
    _name       = cast(str, property(lambda _: 'peaks', lambda _1, _2: None))
    def _refindex(self, kdims):
        if self._reference is None:
            return None
        if self._overlay in ('bead', 'key'):
            return kdims[self._overlay].index(self._reference)
        return 0

    def _convert(self, kdims, ovrs): # pylint: disable=arguments-differ
        ind = self._refindex(kdims)
        if ind is None or ind < 0 or ind >= len(tuple(ovrs)):
            return ovrs

        area = next(iter(ovrs[ind])).to(hv.Area)
        ovrs[ind] = hv.Overlay([area.options(alpha = 0.5)] + list(ovrs[ind]),
                               label = ovrs[ind].label,
                               group = ovrs[ind].group)
        return ovrs

    def dataframe(self, *tasks, transform = None, assign = None, **kwa):
        """
        Concatenates all dataframes obtained through *track.peaks.dataframe*

        See documentation in *track.peaks.dataframe* for other options
        """
        kwa.update(transform = transform, assign = assign)
        return PeaksTracksDictOperator(self).dataframe(*tasks, **kwa)

TracksDictDisplay.addtodoc("""
    * `tracks.peaks` displays peaks per bead and track.""")

__all__: List[str] = []
