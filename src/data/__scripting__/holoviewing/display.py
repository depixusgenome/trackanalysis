#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import sys
from   itertools import chain, repeat
import numpy     as     np
from   ...       import Beads

hv    = sys.modules['holoviews']  # pylint: disable=invalid-name

class Display:
    "displays the beads or cycles"
    @staticmethod
    def concat(itr):
        "concatenates arrays, appending a NaN"
        return np.concatenate(list(chain.from_iterable(zip(itr, repeat([np.NaN])))))

    @staticmethod
    def errormessage(exc, **dims):
        "displays error message"
        args = getattr(exc, 'args', tuple())
        if isinstance(args, (list, tuple)) and len(args) == 2:
            txt = str(exc.args[0]).split('\n')
        else:
            raise RuntimeError("error") from exc

        ovr = hv.Overlay([hv.Text(0.4, len(txt)*.1+.5-i*.1, j)
                          for i, j in enumerate(txt)])
        return ovr.redim(**dims) if len(dims) else ovr

    @staticmethod
    def _create(labels, tpe, overlay, opts, good):
        opts.setdefault('kdims', ['frames'])
        opts.setdefault('vdims', ['z'])
        if isinstance(tpe, str):
            tpe = getattr(hv, tpe) if hasattr(hv, tpe) else getattr(hv, tpe.capitalize())
        if isinstance(labels, str):
            crvs = [tpe(j, label = labels, **opts) for i, j in good]
        elif (len(good) < 3 and labels) or labels is True:
            crvs = [tpe(j, label = f'{i}', **opts) for i, j in good]
        else:
            crvs = [tpe(j, **opts) for _, j in good]
        return crvs[0] if len(crvs) == 1 and overlay is False else hv.Overlay(crvs)

    @classmethod
    def run(cls, itms, labels, tpe, overlay, opts): # pylint: disable=too-many-arguments
        "shows overlayed Curve items"
        try:
            good = tuple((i, j) for i, j in itms if np.any(np.isfinite(j)))
        except Exception as exc: # pylint: disable=broad-except
            return cls.errormessage(exc,
                                    x = opts.get('kdims', ['frames'])[0],
                                    y = opts.get('vdims', ['z'])[0])

        if not overlay:
            good = (('', (cls.concat(np.arange(len(i), dtype = 'f4') for _, i in good),
                          cls.concat(i for _, i in good))),)
        return cls._create(labels, tpe, overlay, opts, good)

    @classmethod
    def cycles(cls, itms, # pylint: disable=too-many-arguments
               kdim    = 'bead',
               labels  = None,
               tpe     = 'curve',
               overlay = True,
               **opts):
        """
        Displays cycles.

        Arguments are:

            * *kdim*: if set to 'bead', then a *holoviews.DynamicMap* is returned,
            displaying beads independently. If set to 'cycle', the map displays cycles
            independently.
            * *labels*: if *False*, no labels are added. If *None*, labels are added
            if 3 or less beads are shown.
            * *tpe*: can be scatter or curve.
            * *overlay*: if *False*, all data is concatenated into one array.
        """
        disp = cls.run
        if kdim == 'cycle':
            keys = list(set([i for _, i in itms.keys() if Beads.isbead(_)]))
            def _percycle(cyc):
                return disp(itms[...,cyc], labels, tpe, overlay, opts)
            fcn  = _percycle
        elif kdim == 'bead':
            keys = list(set([i for i, _ in itms.keys() if Beads.isbead(i)]))
            def _perbead(bead):
                return disp(itms[bead,...], labels, tpe, overlay, opts)
            fcn  = _perbead
        else:
            return disp(itms, labels, tpe, overlay, opts)

        return hv.DynamicMap(fcn, kdims = [kdim]).redim.values(**{kdim: keys})

    @classmethod
    def beads(cls, itms, # pylint: disable=too-many-arguments
              kdim    = 'bead',
              labels  = None,
              tpe     = 'curve',
              overlay = True,
              **opts):
        """
        Displays beads.

        Arguments are:

            * *kdim*: if 'bead', then a *holoviews.DynamicMap* is returned, displaying
            beads independently.
            * *labels*: if *False*, no labels are added. If *None*, labels are added
            if 3 or less beads are shown.
            * *tpe*: can be scatter or curve.
            * *overlay*: if *False*, all data is concatenated into one array.
        """
        disp = cls.run
        if kdim == 'bead':
            beads = list(set([i for i in itms.keys() if itms.isbead(i)]))
            def _fcn(bead):
                return disp(itms[[bead]], labels, tpe, overlay, opts)
            return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)
        return disp(itms, labels, tpe, overlay, opts)
