#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
import sys
from   typing                   import List
from   utils.decoration         import addto
from   utils.logconfig          import getLogger
from   ..tracksdict             import ExperimentList, TracksDict

LOGS  = getLogger(__name__)
hv    = sys.modules['holoviews']  # pylint: disable=invalid-name

@addto(TracksDict)         # type: ignore
def map(self, fcn, kdim = 'oligo', *extra, **kwa):
    "returns a hv.DynamicMap"
    if kdim is not None and kdim not in kwa:
        kwa[kdim] = list(self.keys())

    if 'bead' not in kwa:
        kwa['bead'] = self.beads(*kwa.get(kdim, ()))

    return hv.DynamicMap(fcn, kdims = list(kwa)+list(extra)).redim.values(**kwa)

class TracksDictDisplay:
    "displays a tracksdict"
    @staticmethod
    def _base(itms, name, kwa, label):
        refdims   = kwa.pop('refdims',   True)
        reflayout = kwa.pop('reflayout', 'left')

        args      = dict(kwa)
        fcn       = lambda key, bead, **other: (getattr(itms[key], name)
                                                .display(**kwa, **other)
                                                [bead])

        if 'labels' not in kwa and label:
            fcn = lambda key, bead: (getattr(itms[key], name)
                                     .display(labels = '{}'.format(key if label == 'key' else bead),
                                              **args)
                                     [bead])

        kdims     = dict()
        kdims['key']  = kwa.pop('key')  if 'key'  in kwa else list(itms.keys())
        kdims['bead'] = kwa.pop('bead') if 'bead' in kwa else list(itms.beads(*kdims['key']))
        return kdims, fcn, refdims, reflayout

    @staticmethod
    def _kdimreference(reflayout, kdims, name, reference):
        if reference is None:
            return

        kdims[name] = [i for i in kdims[name] if i != reference]
        if reflayout in ('right', 'top'):
            kdims[name].append(reference)
        else:
            kdims[name].insert(0, reference)

    @staticmethod
    def _all(_, name, fcn, kdims, key):
        if name == 'bead':
            return [fcn(key, i) for i in kdims[name]]
        return [fcn(i, key) for i in kdims[name]]

    @classmethod
    def _overlay(cls, itms, name, reference, overlay, kwa): # pylint: disable=too-many-arguments
        "display overlaying keys"
        kdims, fcn, _, reflayout = cls._base(itms, name, kwa, overlay)
        cls._kdimreference(reflayout, kdims, overlay, reference)
        fcn   = lambda key, _f_ = fcn: hv.Overlay(cls._all(reference, overlay, _f_, kdims, key))
        other = 'key' if overlay == 'bead' else 'bead'
        return hv.DynamicMap(fcn, kdims = [other]).redim.values(bead = kdims[other])

    @classmethod
    def refwithoutoverlay(cls, itms, name, reference, kwa):
        "display without overlay but with reference"
        kdims, fcn, refdims, reflayout = cls._base(itms, name, kwa, None)
        kdims['key'] = [i for i in kdims['key'] if i != reference]
        def _ref(key, bead, __fcn__ = fcn):
            val   = __fcn__(reference, bead).clone(label = reference)
            if refdims:
                val = val.redim(**{i.name: i.clone(label = f'{reference}{i.label}')
                                   for i in val.dimensions()})

            other = __fcn__(key, bead).clone(label = key)
            if reflayout in ('left', 'top'):
                return (val+other).cols(1 if reflayout == 'top' else 2)
            return (other+val).cols(1 if reflayout == 'bottom' else 2)
        return hv.DynamicMap(_ref, kdims = ['key', 'bead']).redim.values(**kdims)

    @classmethod
    def withoutoverlay(cls, itms, name, kwa):
        "display without overlay"
        kdims, fcn = cls._base(itms, name, kwa, None)[:2]
        return hv.DynamicMap(fcn, kdims = ['key', 'bead']).redim.values(**kdims)

    @classmethod
    def run(cls, itms, name, overlay, reference, kwa): # pylint: disable=too-many-arguments
        "displays"
        if overlay in ('key', 'bead'):
            return cls._overlay(itms, name, reference, overlay, kwa)
        if reference is not None:
            return cls.refwithoutoverlay(itms, name, reference, kwa)
        return cls.withoutoverlay(itms, name, kwa)

@addto(TracksDict) # type: ignore
def cycles(self, overlay = None, reference = None, **kwa):
    """
    A hv.DynamicMap showing cycles

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
    return TracksDictDisplay.run(self, 'cycles', overlay, reference, kwa)

@addto(TracksDict) # type: ignore
def measures(self, overlay = None, reference = None, **kwa):
    """
    A hv.DynamicMap showing measures

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
    return TracksDictDisplay.run(self, 'measures', overlay, reference, kwa)

@addto(TracksDict)
def fov(self, *keys, calib = False, layout = True, cols = 2, **opts):
    "displays all fovs"
    if len(keys) == 0:
        keys = self.keys()

    opts['calib'] = calib
    fcn           = lambda key: self[key].fov.display(**opts).relabel(f'{key}')
    if layout:
        return hv.Layout([fcn(i) for i in keys]).cols(cols)
    return hv.DynamicMap(fcn, kdims = ['key']).redim.values(key = list(keys))

@addto(ExperimentList)
def oligomap(self:ExperimentList, oligo, fcn, **kwa):
    "returns a hv.DynamicMap with oligos and beads in the kdims"
    oligos = self.allkeys(oligo)
    beads  = self.available(*oligos)
    LOGS.info(f"{oligos}, {beads}")
    return (hv.DynamicMap(fcn, kdims = ['oligo', 'bead'] + list(kwa))
            .redim.values(oligo = oligos, bead = beads, **kwa))

@addto(ExperimentList)
def keymap(self:ExperimentList, key, fcn, **kwa):
    "returns a hv.DynamicMap with keys in the kdims"
    beads  = self.available(*self.convert(key))
    LOGS.info(f"{key}, {beads}")
    return (hv.DynamicMap(fcn, kdims = ['bead']+list(kwa))
            .redim.values(bead = beads, **kwa))

__all__: List[str] = []
