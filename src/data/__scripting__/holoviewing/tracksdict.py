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
    def _specs():
        return ('refdims',  True), ('reflayout', 'left')

    @classmethod
    def _base(cls, itms, name, reference, overlay, kwa): # pylint: disable=too-many-arguments
        kdims         = dict()
        kdims['key']  = sorted(kwa.pop('key')  if 'key'  in kwa else itms.keys())
        kdims['bead'] = sorted(kwa.pop('bead') if 'bead' in kwa else itms.beads(*kdims['key']))

        specs = {i: kwa.pop(i, j) for i, j in cls._specs()}
        specs.update(reference = reference, name = name, kdims = kdims, overlay = overlay)

        display = getattr(cls, '_'+name, cls._default_display)
        fcn     = lambda key, bead, **other: display(itms, key, bead, specs, **kwa, **other)
        return fcn, specs

    @staticmethod
    def _default_display(itms, key, bead, specs, **kwa):
        data = getattr(itms[key], specs['name'])
        if specs['overlay'] == 'key' and 'labels' not in kwa:
            kwa['labels'] = str(key)
        elif specs['overlay'] == 'bead' and 'labels' not in kwa:
            kwa['labels'] = str(bead)
        return data.display(**kwa)[bead]

    @staticmethod
    def _all(specs, fcn, key):
        if specs['overlay'] == 'bead':
            return [fcn(key, i) for i in specs['kdims'][specs['overlay']]]
        return [fcn(i, key) for i in specs['kdims'][specs['overlay']]]

    @classmethod
    def _overlay(cls, itms, name, reference, overlay, kwa): # pylint: disable=too-many-arguments
        "display overlaying keys"
        fcn, specs = cls._base(itms, name, reference, overlay, kwa)

        if reference:
            kdims          = specs['kdims']
            kdims[overlay] = [i for i in kdims[overlay] if i != reference]
            if specs['reflayout'] in ('right', 'top'):
                kdims[overlay].append(reference)
            else:
                kdims[overlay].insert(0, reference)

        fcn   = lambda key, _f_ = fcn: hv.Overlay(cls._all(specs, _f_, key))
        other = 'key' if overlay == 'bead' else 'bead'
        return hv.DynamicMap(fcn, kdims = [other]).redim.values(bead = specs['kdims'][other])

    @staticmethod
    def _same(_, ref, other):
        return [ref, other]

    @classmethod
    def refwithoutoverlay(cls, itms, name, reference, kwa):
        "display without overlay but with reference"
        fcn, specs   = cls._base(itms, name, reference, False, kwa)
        kdims        = specs['kdims']
        kdims['key'] = [i for i in kdims['key'] if i != reference]
        def _ref(key, bead, __fcn__ = fcn):
            val   = __fcn__(reference, bead).clone(label = reference)
            if specs['refdims']:
                val = val.redim(**{i.name: i.clone(label = f'{reference}{i.label}')
                                   for i in val.dimensions()})

            other = __fcn__(key, bead).clone(label = key)
            if specs['reflayout'] == 'same':
                return hv.Overlay(cls._same(specs, val, other))
            if specs['reflayout'] in ('left', 'top'):
                return (val+other).cols(1 if specs['reflayout'] == 'top' else 2)
            return (other+val).cols(1 if specs['reflayout'] == 'bottom' else 2)
        return hv.DynamicMap(_ref, kdims = ['key', 'bead']).redim.values(**kdims)

    @classmethod
    def withoutoverlay(cls, itms, name, kwa):
        "display without overlay"
        fcn, specs = cls._base(itms, name, None, False, kwa)[:2]
        return hv.DynamicMap(fcn, kdims = ['key', 'bead']).redim.values(**specs['kdims'])

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
def cleancycles(self, overlay = None, reference = None, **kwa):
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
    return TracksDictDisplay.run(self, 'cleancycles', overlay, reference, kwa)

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
