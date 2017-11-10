#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
import sys
from   typing                   import List, Union
from   copy                     import deepcopy

from   scripting.holoviewing    import addto, displayhook, addproperty
from   utils.logconfig          import getLogger
from   ...views                 import isellipsis, BEADKEY
from   ...tracksdict            import TracksDict
from   ..tracksdict             import ExperimentList
from   .display                 import BasicDisplay

LOGS  = getLogger(__name__)
hv    = sys.modules['holoviews']  # pylint: disable=invalid-name

class TracksDictDisplay(BasicDisplay,
                        cycles      = (TracksDict, dict(name = 'cycles')),
                        cleancycles = (TracksDict, dict(name = 'cleancycles')),
                        measures    = (TracksDict, dict(name = 'measures'))
                       ):
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
    _beads:     List[BEADKEY]          = None
    _keys:      List[str]              = None
    _name:      str                    = None
    _overlay:   str                    = None
    _reference: str                    = None
    _refdims                           = True
    _reflayout                         = 'left'
    _labels:    Union[None, bool, str] = True
    KEYWORDS                           = BasicDisplay.KEYWORDS | frozenset(locals())
    def __getitem__(self, values):
        if isinstance(values, tuple):
            tracks, beads = values
            if not isinstance(tracks, list) and tracks in self._items:
                tracks = [tracks]

            if isinstance(tracks, list) and isinstance(beads, int):
                beads = [beads]
            elif (isinstance(beads, list)
                  and not isinstance(tracks, list)
                  and not isellipsis(tracks)):
                tracks = [tracks]

            self._keys  = None     if isellipsis(tracks) else list(tracks)
            self._beads = (None    if isellipsis(beads)  else
                           [beads] if isinstance(beads, (int, str)) else
                           list(beads))

        elif isinstance(values, list):
            if all(i in self._items for i in values):
                self._keys = None if isellipsis(values) else values
            else:
                self._beads = None if isellipsis(values) else values

        elif isellipsis(values):
            self._keys  = None
            self._beads = None

        elif values in self._items:
            self._keys  = [values]
        else:
            raise KeyError("Could not slice the display")
        return self

    def _base(self):
        itms  = self._items
        kwa   = deepcopy(self._opts)

        kdims         = dict()
        keys          = kwa.pop('key')  if 'key'  in kwa else self._keys
        beads         = kwa.pop('key')  if 'key'  in kwa else self._beads
        if beads is None:
            kdims['key']  = sorted(itms.keys()) if keys is None else keys
            kdims['bead'] = sorted(itms.availablebeads(*kdims['key']))
        else:
            kdims['bead'] = beads
            kdims['key']  = sorted(itms.availablekeys(*beads)) if keys is None else keys

        if self._reference is not None:
            key = 'bead' if self._overlay == 'bead' else 'key'
            kdims[key] = [i for i in kdims[key] if i != self._reference]
            kdims[key].insert(0, self._reference)

        disp = getattr(self, '_'+self._name, self._default_display)
        fcn  = lambda key, bead, **other: disp(itms, key, bead, kdims, **kwa, **other)
        return fcn, kdims

    def _default_kargs(self, key, bead, kwa):
        if self._labels is True and self._overlay in ('key', 'bead'):
            kwa.setdefault('labels', str(key) if self._overlay == 'key' else str(bead))
        elif isinstance(self._labels, str):
            kwa.setdefault('labels', self._labels)

    def _default_display(self, itms, key, bead, _, **kwa):
        self._default_kargs(key, bead, kwa)
        data = getattr(itms[key], self._name, itms[key]).display(**kwa)
        return data.getmethod()(bead)

    @staticmethod
    def _convert(_, elems):
        return elems

    @staticmethod
    def _same(ref, other):
        return [ref, other]

    def _overlayed_method(self, key):
        fcn, kdims = self._base()
        if self._overlay == 'bead':
            crvs = [fcn(key, i, neverempty = True) for i in kdims[self._overlay]]
        else:
            crvs = [fcn(i, key, neverempty = True) for i in kdims[self._overlay]]
        return hv.Overlay(self._convert(kdims, crvs))

    def _reference_method(self, key, bead):
        fcn, kdims = self._base()
        val        = fcn(self._reference, bead, neverempty = True, labels = self._reference)
        if self._refdims:
            val = val.redim(**{i.name: i.clone(label = f'{self._reference}{i.label}')
                               for i in val.dimensions()})

        label = (key    if self._labels is None  else
                 False  if self._labels is False else
                 'key')
        other = fcn(key, bead, neverempty = True, labels = label)
        if self._reflayout == 'same':
            return hv.Overlay(self._convert(kdims, [val, other]))
        if self._reflayout in ('left', 'top'):
            return (val+other).cols(1 if self._reflayout == 'top' else 2)
        return (other+val).cols(1 if self._reflayout == 'bottom' else 2)

    def getmethod(self):
        "Returns the method used by the dynamic map"
        return (self._overlayed_method if self._overlay in ('key', 'bead') else
                self._reference_method if self._reference is not None      else
                self._base()[0])

    def getredim(self):
        "Returns the method used by the dynamic map"
        kdims = self._base()[1]

        if self._overlay in ('key', 'bead'):
            kdims.pop(self._overlay)

        key = 'bead' if self._overlay == 'bead' else 'key'
        if self._reference in kdims.get(key, []):
            kdims[key] = [i for i in kdims[key] if i != self._reference]

        if set(kdims) == {'key', 'bead'}:
            return [(i, kdims[i]) for i in ('key', 'bead')]
        return kdims

@displayhook
@addproperty(TracksDict, 'fov')
class TracksDictFovDisplayProperty:
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
    def __init__(self, dico):
        self.tracks = dico
        self._keys  = None

    def __getitem__(self, values):
        if isinstance(values, list):
            self._keys = values
        elif isellipsis(values):
            self._keys = None
        elif values in self._keys:
            self._keys = [values]
        else:
            raise KeyError("Could not slice the display")
        return self

    def display(self, *keys, calib = False, layout = False, cols = 2, **opts):
        "displays measures for a TracksDict"
        if len(keys) == 0:
            keys = self._keys if self._keys else self.tracks.keys()

        opts['calib'] = calib
        fcn           = lambda key: self.tracks[key].fov.display(**opts).relabel(f'{key}')
        if layout:
            return hv.Layout([fcn(i) for i in keys]).cols(cols)
        return hv.DynamicMap(fcn, kdims = ['key']).redim.values(key = list(keys))

@addto(TracksDict)         # type: ignore
def display(self):
    "Returns a table with some data"
    return hv.Table(self.dataframe(), kdims = ['key'])

@addto(TracksDict)         # type: ignore
def map(self, fcn, kdim = 'oligo', *extra, **kwa):
    "returns a hv.DynamicMap"
    if kdim is not None and kdim not in kwa:
        kwa[kdim] = list(self.keys())

    if 'bead' not in kwa:
        kwa['bead'] = self.beads(*kwa.get(kdim, ()))

    return hv.DynamicMap(fcn, kdims = list(kwa)+list(extra)).redim.values(**kwa)

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
