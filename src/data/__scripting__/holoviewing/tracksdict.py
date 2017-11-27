#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
from   typing                   import List, Union
from   functools                import partial, wraps

from   scripting.holoviewing    import addto, displayhook, addproperty, hv
from   ...views                 import isellipsis, BEADKEY
from   ...tracksdict            import TracksDict
from   .display                 import BasicDisplay

_TDOC = (
    """
    ## Displays

    A number of displays are available:

    * `tracks`: displays a table with a number of characteristics per track. It's
    a simple rendering of the dataframe created through `track.dataframe()`.
    * `tracks.secondaries.temperatures()` creates a display of track temperatures.
    * `tracks.secondaries.vcap()` creates a display of vcap versus zmag per track.""")

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
    @staticmethod
    def addtodoc(new):
        "adds display documentation"
        from ..tracksdict import TracksDict as _TDict
        doc = _TDict.__doc__
        if _TDOC not in doc:
            doc += _TDOC
        ind = doc.find(_TDOC)+len(_TDOC)
        _TDict.__doc__ = doc[:ind]+new+doc[ind:]

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
        kdims = self._default_kdims()
        return partial(self._default_display, kdims), kdims

    def _default_kdims(self):
        kdims = dict()
        keys  = self._keys
        beads = self._beads
        itms  = self._items
        if beads is None:
            kdims['key']  = sorted(itms.keys()) if keys is None else keys
            kdims['bead'] = sorted(itms.availablebeads(*kdims['key']))
        else:
            kdims['bead'] = beads
            kdims['key']  = sorted(itms.commonkeys(*beads)) if keys is None else keys

        if self._reference is not None:
            key = 'bead' if self._overlay == 'bead' else 'key'
            kdims[key] = [i for i in kdims[key] if i != self._reference]
            kdims[key].insert(0, self._reference)
        return kdims

    def _default_kargs(self, key, bead, kwa):
        if self._opts:
            tmp, kwa = kwa, dict(self._opts)
            kwa.update(tmp)
        if self._labels is True and self._overlay in ('key', 'bead'):
            kwa.setdefault('labels', str(key) if self._overlay == 'key' else str(bead))
        elif isinstance(self._labels, str):
            kwa.setdefault('labels', self._labels)

    def _default_display(self, _, key, bead, **kwa):
        self._default_kargs(key, bead, kwa)
        data = getattr(self._items[key], self._name, self._items[key]).display(**kwa)
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

class TracksDictDisplayProperty:
    "Helper class for display some track property"
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

    def _tomap(self, attr, *keys, layout = False, cols = 2, **kwa):
        mykeys = list(keys       if keys       else
                      self._keys if self._keys else
                      self.tracks.keys())

        fcn = partial(attr, **kwa) if kwa else attr
        if layout:
            return hv.Layout([fcn(i) for i in mykeys]).cols(cols)
        dmap = hv.DynamicMap(fcn, kdims = ['key']).redim.values(key = mykeys)
        return dmap

    @classmethod
    def apply(cls, fcn):
        "creates a method mapping a track display to a hv.DynamicMap"
        @wraps(fcn)
        def _wrapped(self, *keys, layout = False, cols = 2, **kwa):
            cur = partial(fcn, self, **kwa)
            # pylint: disable=protected-access
            return self._tomap(cur, *keys, layout = layout, cols = cols)
        return _wrapped

@displayhook
@addproperty(TracksDict, 'fov')
class TracksDictFovDisplayProperty(TracksDictDisplayProperty):
    """
    A hv.DynamicMap showing the field of views.

    Options are:

    * *calib* shows the bead calibration files
    * *layout* uses a layout rather than a dynamic map
    * *cols* is the number of columns in the layout
    """
    @TracksDictDisplayProperty.apply
    def display(self, key, calib = False, **opts):
        "displays measures for a TracksDict"
        return self.tracks[key].fov.display(calib = calib, **opts).relabel(f'{key}')
    display.__doc__ = __doc__

@addto(TracksDict)         # type: ignore
def display(self):
    "Returns a table with some data"
    return hv.Table(self.dataframe(), kdims = ['key'])

@addproperty(TracksDict, 'secondaries')
class TracksDictSecondariesDisplayProperty(TracksDictDisplayProperty):
    """
    Allows displaying temperatures or vcap

    Options are:

    * *layout* uses a layout rather than a dynamic map
    * *cols* is the number of columns in the layout
    """
    @TracksDictDisplayProperty.apply
    def temperatures(self, key):
        "displays all temperatures"
        return self.tracks[key].secondaries.display.temperatures()
    temperatures.__doc__ = __doc__.replace(' or vcap', '')

    @TracksDictDisplayProperty.apply
    def vcap(self, key):
        "displays all zmag versus vcap"
        return self.tracks[key].secondaries.display.vcap()
    vcap.__doc__ = __doc__.replace('temperatures or', 'zmag versus')

__all__: List[str] = []
