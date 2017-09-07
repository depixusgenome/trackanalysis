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
        kwa['bead'] = self.keys(*kwa.get(kdim, ()))

    return hv.DynamicMap(fcn, kdims = list(kwa)+list(extra)).redim.values(**kwa)

def _display(self, name, overlay, reference, kwa):
    "returns a hv.DynamicMap showing cycles"
    refdims   = kwa.pop('refdims',   True)
    reflayout = kwa.pop('reflayout', 'left')

    kdims = dict()
    kdims['key']  = kwa.pop('key')  if 'key'  in kwa else list(self.keys())
    kdims['bead'] = kwa.pop('bead') if 'bead' in kwa else list(self.beads(*kdims['key']))

    fcn = lambda key, bead: getattr(self[key], name).display(**kwa)[bead]
    if overlay == 'bead':
        if 'labels' not in kwa:
            fcn = lambda key, bead: (getattr(self[key], name)
                                     .display(labels = f'{key}', **kwa)
                                     [bead])
        if reference is not None:
            kdims['bead'] = [i for i in kdims['bead'] if i != reference]
            if reflayout in ('right', 'top'):
                kdims['bead'].append(reference)
            else:
                kdims['bead'].insert(0, reference)

        def _allbeads(key):
            return hv.Overlay([fcn(key, i) for i in kdims['bead']])
        return hv.DynamicMap(_allbeads, kdims = ['key']).redim.values(key = kdims['key'])

    if overlay == 'key':
        if reference is not None:
            kdims['key'] = [i for i in kdims['key'] if i != reference]
            if reflayout in ('right', 'top'):
                kdims['key'].append(reference)
            else:
                kdims['key'].insert(0, reference)

        if 'labels' not in kwa:
            fcn = lambda key, bead: (getattr(self[key], name)
                                     .display(labels = f'{key}', **kwa)
                                     [bead])
        def _allkeys(bead):
            return hv.Overlay([fcn(i, bead) for i in kdims['key']])
        return hv.DynamicMap(_allkeys, kdims = ['bead']).redim.values(bead = kdims['bead'])

    if reference is not None:
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
        fcn = _ref
    return hv.DynamicMap(fcn, kdims = ['key', 'bead']).redim.values(**kdims)

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
    return _display(self, 'cycles', overlay, reference, kwa)

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
    return _display(self, 'measures', overlay, reference, kwa)

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
