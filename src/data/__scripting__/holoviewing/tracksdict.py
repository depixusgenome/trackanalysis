#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
import sys
from   typing                   import List
from   scripting.holoviewing    import addto, displayhook
from   utils.logconfig          import getLogger
from   ...views                 import isellipsis
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

@displayhook
class TracksDictDisplay:
    "displays a tracksdict"
    def __init__(self, dico, name):
        self.tracks = dico
        self.name   = name
        self.beads  = None
        self.keys   = None

    def __getitem__(self, values):
        if isinstance(values, tuple):
            tracks, beads = values
            if not isinstance(tracks, list) and tracks in self.tracks:
                trk = self.tracks[tracks]
                return getattr(trk, self.name, trk)[beads]

            if isinstance(tracks, list) and isinstance(beads, int):
                beads = [beads]
            elif isinstance(beads, list) and not isinstance(tracks, list):
                tracks = [tracks]

            self.keys  = None if isellipsis(tracks) else tracks
            self.beads = None if isellipsis(beads) else beads

        elif isinstance(values, list):
            if all(i in self.tracks for i in values):
                self.keys = None if isellipsis(values) else values
            else:
                self.beads = None if isellipsis(values) else values

        elif isellipsis(values):
            self.tracks = None

        elif values in self.tracks:
            trk = self.tracks[values]
            itm = getattr(trk, self.name, trk)
            return itm[self.beads] if self.beads else itm

        else:
            raise KeyError("Could not slice the display")
        return self

    def __add__(self, other):
        return self.display() + (other if isinstance(other, hv.Element) else other.display())

    def __mul__(self, other):
        return self.display() * (other if isinstance(other, hv.Element) else other.display())

    def __lshift__(self, other):
        return self.display() << (other if isinstance(other, hv.Element) else other.display())

    def __rshift__(self, other):
        return self.display() >> (other if isinstance(other, hv.Element) else other.display())

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
        print(type(itms), type(itms[key]))
        data = getattr(itms[key], specs['name'], itms[key])
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

    def display(self, overlay = None, reference = None, **kwa):
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
        if self.beads:
            kwa.setdefault('bead', self.beads)
        if self.keys:
            kwa.setdefault('key', self.keys)
        return self.run(self.tracks, self.name, overlay, reference, kwa)

@addto(TracksDict) # type: ignore
@property
def cycles(self):
    "displays cycles"
    return TracksDictDisplay(self, 'cycles')

@addto(TracksDict) # type: ignore
@property
def cleancycles(self):
    "displays cleaned cycles"
    return TracksDictDisplay(self, 'cleancycles')

@addto(TracksDict) # type: ignore
@property
def measures(self):
    "displays cleaned measures"
    return TracksDictDisplay(self, 'measures')

@displayhook
class TracksDictFovDisplayProperty:
    "displays measures for a TracksDict"
    def __init__(self, dico):
        self.tracks = dico
        self.keys   = None

    def __getitem__(self, values):
        if isinstance(values, list):
            self.tracks = values
        elif isellipsis(values):
            self.tracks = None
        elif values in self.tracks:
            return self.tracks[values].fov
        else:
            raise KeyError("Could not slice the display")
        return self

    def display(self, *keys, calib = False, layout = False, cols = 2, **opts):
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
        if len(keys) == 0:
            keys = self.keys if self.keys else self.tracks.keys()

        opts['calib'] = calib
        fcn           = lambda key: self.tracks[key].fov.display(**opts).relabel(f'{key}')
        if layout:
            return hv.Layout([fcn(i) for i in keys]).cols(cols)
        return hv.DynamicMap(fcn, kdims = ['key']).redim.values(key = list(keys))

@addto(TracksDict)  # type: ignore
@property
def fov(self):
    "displays all fovs"
    return TracksDictFovDisplayProperty(self)

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
