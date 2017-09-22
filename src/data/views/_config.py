#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds methods for configuring a TracksView"
from   inspect          import signature
from   copy             import copy as shallowcopy
from   itertools        import product
from   functools        import partial
from   typing           import Tuple, Iterable, Union, List, TypeVar, Hashable, cast
import numpy            as     np

from   utils            import isfunction
from   ._dict           import TRACK_VIEW, TransformedTrackView, isint, isellipsis

def _m_copy(_, item):
    "Copies the data"
    return item[0], np.copy(item[1])

def _m_torange(sli):
    start, stop, step = sli.start, sli.stop, sli.step
    if stop is None:
        raise IndexError("An exact number must be provided for stop")
    return range(0 if start is None else start, stop, 1 if step is None else step)

_m_INDEX = int, cast(type, np.integer), str, tuple

CSelf = TypeVar('CSelf',  bound = 'TrackViewConfigMixin')
class TrackViewConfigMixin(Iterable): # pylint: disable=invalid-name
    "Adds methods for configuring a TracksView"
    data:      TRACK_VIEW             = None
    selected:  List                   = None
    discarded: List                   = None
    beadsonly                         = False
    actions:   List                   = []
    parents:   Union[Tuple, Hashable] = tuple()
    _COPY:     bool                   = None
    def __init__(self, **kw) -> None:
        super().__init__()
        get = lambda x: kw.get(x, shallowcopy(getattr(self.__class__, x)))
        self.data      = get('data')
        self.parents   = get('parents')
        self.actions   = get('actions')
        self.beadsonly = get('beadsonly')

        self.__selection('selected',  get('selected'),  False)
        self.__selection('discarded', get('discarded'), False)

        if kw.get('copy', self._COPY):
            self.actions.append(getattr(self, 'copy', _m_copy))

        if kw.get('samples', None) is not None:
            samples = kw['samples']
            self.actions.append(partial(self.__samples, samples))

    copy = staticmethod(_m_copy)    # type: ignore

    @staticmethod
    def isbead(key) -> bool:
        "returns whether the key is one for a bead"
        return ((isinstance(key, tuple)
                 and len(key) > 0
                 and isint(key[0])
                ) or isint(key))

    def withbeadsonly(self:CSelf, beadsonly = True) -> CSelf:
        "discards all but beads"
        self.beadsonly = beadsonly
        return self

    @staticmethod
    def __samples(samples, _, info):
        return info[0], info[1][samples]

    def withsamples(self:CSelf, samples) -> CSelf:
        "specifies that only some samples should be taken"
        if samples is not None:
            self.actions.append(partial(self.__samples, samples))
        return self

    def withcopy(self:CSelf, cpy:bool = True) -> CSelf:
        "specifies that a copy of the data should or shouldn't be made"
        fcn = getattr(self, 'copy', _m_copy)
        if cpy and fcn not in self.actions:
            self.actions.append(fcn)
        elif not cpy and fcn in self.actions:
            self.actions.remove(fcn)
        return self

    @staticmethod
    def __f_all(_, fcn, items):
        return items[0], fcn(items[1])

    @staticmethod
    def __f_beads(fcn, frame, items):
        return items[0], (fcn(items[1]) if frame.isbead(items[0]) else items[1])

    @staticmethod
    def __a_beads(fcn, frame, items):
        return fcn(frame, items) if frame.isbead(items[0]) else items

    def withfunction(self:CSelf, fcn = None, clear = False, beadsonly = False) -> CSelf:
        "Adds an action with fcn taking a value as single argument"
        if clear:
            self.actions = []

        if fcn is None:
            return self

        try:
            signature(fcn).bind(1)
        except TypeError as exc:
            msg = f'Function {fcn} should have a single positional argument'
            raise TypeError(msg) from exc

        if beadsonly:
            self.actions.append(partial(self.__f_all, fcn))
        else:
            self.actions.append(partial(self.__f_beads, fcn))
        return self

    def withaction(self:CSelf, fcn = None, clear = False, beadsonly = False) -> CSelf:
        "Adds an action with fcn taking a (key, value) pair as single argument"
        if clear:
            self.actions = []

        if fcn is None:
            return self

        try:
            signature(fcn).bind(1, 2)
        except TypeError as exc:
            msg = (f'Function {fcn} should have two'
                   ' positional arguments: TrackView, Tuple[key, value]')
            raise TypeError(msg) from exc

        self.actions.append(fcn if beadsonly else partial(self.__a_beads, fcn))
        return self

    def withdata(self:CSelf, dat, fcn = None) -> CSelf:
        "sets the data"
        if fcn is None and callable(dat) and not hasattr(dat, '__getitem__'):
            dat, fcn  = self.data, dat

        if fcn is None:
            self.data = dat
        else:
            self.data = TransformedTrackView(fcn, dat, self)
        return self

    def selecting(self:CSelf, cyc, clear = False) -> CSelf:
        "selects ids over which to iterate. See class doc."
        return self.__selection('selected', cyc, clear)

    def discarding(self:CSelf, cyc, clear = False) -> CSelf:
        "selects ids to discard. See class doc."
        return self.__selection('discarded', cyc, clear)

    def __selection(self:CSelf, attr, cyc, clear) -> CSelf:
        if not isinstance(cyc, List) and isellipsis(cyc):
            setattr(self, attr, None)
            return self

        if clear:
            setattr(self, attr, None)

        if getattr(self, attr) is None:
            setattr(self, attr, [])

        if isinstance(cyc, tuple):
            if all(isinstance(i, _m_INDEX) or isellipsis(i) for i in cyc):
                getattr(self, attr).append(cyc)
            else:
                vals = ((i,)          if (isinstance(i, _m_INDEX) or isellipsis(i)) else
                        _m_torange(i) if isinstance(i, slice)                        else
                        i   for i in cyc)
                getattr(self, attr).extend(product(*vals))

        elif isinstance(cyc, _m_INDEX) or isfunction(cyc):
            getattr(self, attr).append(cyc)

        elif isinstance(cyc, slice):
            getattr(self, attr).extend(_m_torange(cyc))
        else:
            getattr(self, attr).extend(cyc)

        if len(getattr(self, attr)) == 0:
            setattr(self, attr, None)
        return self

    @staticmethod
    def __act(actions, frame, item):
        for action in actions:
            item = action(frame, item)
        return item

    def getaction(self, actions = None):
        "returns a function performing all actions"
        if actions is None:
            actions = self.actions

        return (partial(self.__act, actions) if len(actions) > 1  else
                actions[0]                   if len(actions) == 1 else
                None)
