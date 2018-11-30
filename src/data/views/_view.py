#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds easy access to cycles and events"
from    copy        import copy as shallowcopy
from    typing      import (Optional, Tuple, Union, Any, Sequence, TypeVar,
                            Iterable, Iterator, Generator, Type, cast)
import  numpy as np

from    utils       import initdefaults, isfunction
from    model       import Level
from    ._config    import TrackViewConfigMixin
from    ._dict      import (ITrackView, # pylint: disable=protected-access
                            isellipsis, _m_NONE)

_m_KEYS  = int, cast(type, np.integer), str
TSelf    = TypeVar('TSelf', bound = 'TrackView')
class TrackView(TrackViewConfigMixin, ITrackView):
    "Class for iterating over beads or creating a new list of data"
    level      = Level.none
    track: Any = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kw) -> None:
        super().__init__(**kw)

    def _keys(self, sel:Optional[Sequence]) -> Iterable:
        itr    = iter(cast(dict, self.data).keys())
        if sel is not None:
            keys = frozenset(itr)
            itr  = (i for i in sel if i in keys)
        yield from itr

    def _iter(self, sel = None) -> Iterator[Tuple[Any,Any]]:
        if sel is None:
            sel = self.selected
        if sel is None and isinstance(self.data, dict):
            yield from self.data.items()   # pylint: disable=no-member
        else:
            yield from ((bead, cast(dict, self.data)[bead]) for bead in self.keys(sel))

    def __copy__(self):
        other = type(self).__new__(type(self))  # type: ignore
        other.__dict__.update(track = self.track,
                              **{i: shallowcopy(j)
                                 for i, j in self.__dict__.items() if i != 'track'})
        return other

    def __iter__(self) -> Iterator[Tuple[Any, np.ndarray]]:
        self.__unlazyfy()
        act = self.getaction()
        if act is None:
            yield from (col      for col in self._iter())
        else:
            yield from (act(self, col) for col in self._iter())

    def __getitem__(self:TSelf, keys) -> Union[TSelf, np.ndarray]:
        if (isellipsis(keys)
                or (isinstance(keys, tuple) and all(isellipsis(i) for i in keys))):
            return shallowcopy(self)

        if (isinstance(keys, _m_KEYS)
                or (isinstance(keys, tuple)
                    and all(isinstance(i, _m_KEYS) for i in keys))):
            # this is NOT a slice
            return self.get(keys)

        # consider this a slice
        cpy = shallowcopy(self)
        return (cpy.new() if cpy.selected else cpy).selecting(keys)

    def freeze(self):
        "returns data with all treatments applied"
        data = dict(self)
        for i, j in data.items():
            if isinstance(j, Generator):
                data[i] = np.array(tuple(j), dtype = 'O')

        tpe = self._freeze_type()
        return self.new(tpe, data = data)

    def new(self:TSelf, tpe: Optional[type] = None, **kwa) -> TSelf:
        "returns a item containing self in the data field"
        kwa.setdefault('track',     self.track)
        kwa.setdefault('data',      self)
        kwa.setdefault('cycles',    getattr(self, 'cycles', None))
        kwa.setdefault('parents',   self.parents)
        return (type(self) if tpe is None else tpe)(**kwa)

    def keys(self, sel :Optional[Sequence] = None) -> Iterator:
        "returns accepted keys"
        self.__unlazyfy()
        if sel is None:
            sel = self.selected
        if self.discarded is None:
            yield from self._keys(sel)
        else:
            disc = frozenset(self._keys(self.discarded))
            yield from (key for key in self._keys(sel) if key not in disc)

    def values(self) -> Iterator[np.ndarray]:
        "returns the values only"
        yield from (i for _, i in self.__iter__())

    def get(self, key, default = _m_NONE):
        "get an item"
        if default is _m_NONE:
            vals = next(self._iter(sel = [key]))
        else:
            vals = next(self._iter(sel = [key]), default)
            if vals is default:
                return default

        act = self.getaction()
        if act is not None:
            return act(self, vals)[1]
        return vals[1]

    def phaseposition(self, phase: int, ibead:int) -> Optional[float]:
        "Return the median position for a given phase"
        fcn = getattr(self.track, 'phaseposition', None)
        return fcn(phase, ibead) if callable(fcn) else None # pylint: disable=not-callable

    @staticmethod
    def _freeze_type():
        return TrackView

    def __unlazyfy(self):
        for name, val in self.__dict__.items():
            if isfunction(val):
                setattr(self, name, val(self))

        for attr in ('selected', 'discarded'):
            # pylint: disable=not-an-iterable
            old = getattr(self, attr)
            if old is None or all(not isfunction(i) for i in old):
                continue

            method = getattr(self, attr[:-2]+'ing')
            method(None)
            for i in old:
                method(i(self) if isfunction(i) else i)

        if self.data is None:
            self.data = shallowcopy(self.track.data)

TrackViewType = TypeVar('TrackViewType', bound = TrackView)
def selectparent(self: TrackViewType, tpe: Type[TrackViewType]) -> Optional[TrackViewType]:
    "returns the config for the event creation"
    dummy = dict() # type: ignore
    evts  = getattr(self, 'data', dummy)
    while not isinstance(evts, (dict, tpe)):
        evts = getattr(evts, 'data', dummy)
    if isinstance(evts, tpe):
        while isinstance(getattr(evts, 'data', dummy), tpe):
            evts = getattr(evts, 'data', dummy)
        return evts
    return None
