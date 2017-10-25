#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
import sys
from   typing                   import List
from   copy                     import deepcopy
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
    _beads     = None
    _keys      = None
    _name      = None
    _overlay   = '2d'
    _reference = None
    def __init__(self, dico, **opts):
        self._items     = dico
        get             = lambda x: opts.pop(x, getattr(self.__class__, '_'+x))
        self._name      = get('name')
        self._beads     = get('beads')
        self._keys      = get('keys')
        self._overlay   = get('overlay')
        self._reference = get('reference')
        self._opts      = opts

    def config(self, name = ...):
        "returns the config"
        cnf = deepcopy(self._opts)
        cnf.update({i[1:]: deepcopy(j) for i, j in self.__dict__.items()
                    if (i not in ('_opts', '_items') and
                        len(i) > 2 and i[0] == '_'   and
                        i[1].lower() == i[1])})
        return cnf if name is Ellipsis else cnf[name]

    def __call__(self, **opts):
        default = self.__class__(self._items).config()
        config  = {i: j for i, j in self.config().items() if j != default[i]}
        config.update(opts)
        return self.__class__(self._items, **config)

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
            self._items = None

        elif values in self._items:
            trk = self._items[values]
            itm = getattr(trk, self._name, trk)
            return itm[self._beads] if self._beads else itm

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
    def _specs(_):
        return ('refdims',  True), ('reflayout', 'left')

    def _base(self):
        itms  = self._items
        kwa   = deepcopy(self._opts)

        kdims         = dict()
        kdims['key']  = sorted(kwa.pop('key')  if 'key'  in kwa else
                               self._keys      if self._keys    else
                               itms.keys())
        kdims['bead'] = sorted(kwa.pop('bead') if 'bead' in kwa else
                               self._beads     if self._beads   else
                               itms.beads(*kdims['key']))
        if self._reference is not None:
            key = 'bead' if self._overlay == 'bead' else 'key'
            if self._reference not in kdims[key]:
                kdims[key].insert(0, self._reference)

        specs = {i: kwa.pop(i, j) for i, j in self._specs(kwa)}
        specs.update(reference = self._reference,
                     name      = self._name,
                     kdims     = kdims,
                     overlay   = self._overlay)

        display = getattr(self, '_'+self._name, self._default_display)
        fcn     = lambda key, bead, **other: display(itms, key, bead, specs, **kwa, **other)
        return fcn, specs

    @staticmethod
    def _default_display(itms, key, bead, specs, **kwa):
        if specs['overlay'] == 'key' and 'labels' not in kwa:
            kwa['labels'] = str(key)
        elif specs['overlay'] == 'bead' and 'labels' not in kwa:
            kwa['labels'] = str(bead)

        data = getattr(itms[key], specs['name'], itms[key]).display(**kwa)
        return data.getmethod()(bead)

    @staticmethod
    def _all(specs, fcn, key, **opts):
        if specs['overlay'] == 'bead':
            return [fcn(key, i, **opts) for i in specs['kdims'][specs['overlay']]]
        return [fcn(i, key, **opts) for i in specs['kdims'][specs['overlay']]]

    @staticmethod
    def _same(_, ref, other):
        return [ref, other]

    def getmethod(self):
        "Returns the method used by the dynamic map"
        fcn, specs = self._base()

        if self._overlay in ('key', 'bead'):
            def _over(key, _fcn_ = fcn):
                return hv.Overlay(self._all(specs, _fcn_, key, neverempty = True))
            return _over

        if self._reference is not None:
            def _ref(key, bead, _fcn_ = fcn):
                val   = (_fcn_(self._reference, bead, neverempty = True)
                         .clone(label = self._reference))
                if specs['refdims']:
                    val = val.redim(**{i.name: i.clone(label = f'{self._reference}{i.label}')
                                       for i in val.dimensions()})

                other = _fcn_(key, bead, neverempty = True).clone(label = key)
                if specs['reflayout'] == 'same':
                    return hv.Overlay(self._same(specs, val, other))
                if specs['reflayout'] in ('left', 'top'):
                    return (val+other).cols(1 if specs['reflayout'] == 'top' else 2)
                return (other+val).cols(1 if specs['reflayout'] == 'bottom' else 2)
            return _ref

        return fcn

    def getredim(self):
        "Returns the method used by the dynamic map"
        kdims = self._base()[1]['kdims']

        if self._overlay in ('key', 'bead'):
            kdims.pop(self._overlay)

        key = 'bead' if self._overlay == 'bead' else 'key'
        if self._reference in kdims.get(key, []):
            kdims[key] = [i for i in kdims[key] if i != self._reference]

        return kdims

    def display(self):
        "displays"
        fcn   = self.getmethod()
        kdims = self.getredim()
        if set(kdims) == {'key', 'bead'}:
            vals = ['key', 'bead']
        else:
            vals = [i for i, _ in getattr(kdims, 'items', lambda: kdims)()]

        return hv.DynamicMap(fcn, kdims = vals).redim.values(**dict(kdims))

@addto(TracksDict) # type: ignore
@property
def cycles(self):
    "displays cycles"
    return TracksDictDisplay(self, name = 'cycles')

@addto(TracksDict) # type: ignore
@property
def cleancycles(self):
    "displays cleaned cycles"
    return TracksDictDisplay(self, name = 'cleancycles')

@addto(TracksDict) # type: ignore
@property
def measures(self):
    "displays cleaned measures"
    return TracksDictDisplay(self, name = 'measures')

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
