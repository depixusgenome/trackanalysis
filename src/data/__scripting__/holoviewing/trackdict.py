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
from   ..trackdict              import ExperimentList, TracksDict

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

def _display(self, name, overlay, kwa):
    "returns a hv.DynamicMap showing cycles"
    kdims = dict()
    kdims['key']  = kwa.pop('key')  if 'key'  in kwa else list(self.keys())
    kdims['bead'] = kwa.pop('bead') if 'bead' in kwa else list(self.beads(*kdims['key']))

    fcn = lambda key, bead: getattr(self[key], name).display(**kwa)[bead]
    if overlay == 'bead':
        if 'labels' not in kwa:
            fcn = lambda key, bead: (getattr(self[key], name)
                                     .display(labels = f'{key}', **kwa)
                                     [bead])
        def _allbeads(key):
            return hv.Overlay([fcn(key, i) for i in kdims['bead']])
        return hv.DynamicMap(_allbeads, kdims = ['key']).redim.values(key = kdims['key'])

    if overlay == 'key':
        if 'labels' not in kwa:
            fcn = lambda key, bead: (getattr(self[key], name)
                                     .display(labels = f'{key}', **kwa)
                                     [bead])
        def _allkeys(bead):
            return hv.Overlay([fcn(i, bead) for i in kdims['key']])
        return hv.DynamicMap(_allkeys, kdims = ['bead']).redim.values(bead = kdims['bead'])

    fcn = lambda key, bead: getattr(self[key], name).display(**kwa)[bead]
    return hv.DynamicMap(fcn, kdims = ['bead', 'key']).redim.values(**kdims)

@addto(TracksDict) # type: ignore
def cycles(self, overlay = None, **kwa):
    "returns a hv.DynamicMap showing cycles"
    return _display(self, 'cycles', overlay, kwa)

@addto(TracksDict) # type: ignore
def measures(self, overlay = None, **kwa):
    "returns a hv.DynamicMap showing measures"
    return _display(self, 'measures', overlay, kwa)

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
