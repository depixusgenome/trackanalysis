#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds methods for configuring a TracksView"
from   inspect          import signature
from   copy             import copy as shallowcopy
from   itertools        import product
from   functools        import wraps
from   typing           import Tuple, Union, List, TypeVar, Hashable, cast
import numpy            as     np

from   utils            import isfunction
from   ._dict           import (TRACK_VIEW, # pylint: disable=protected-access
                                TransformedTrackView, _m_ALL, _m_INTS, _m_ellipsis)

def _m_copy(item):
    "Copies the data"
    return item[0], np.copy(item[1])

def _m_check_action_sig(fcn):
    sig = signature(fcn)
    try:
        sig.bind(1)
    except TypeError as exc:
        msg = 'Function should have a single positional argument'
        raise TypeError(msg) from exc

def _m_torange(sli):
    start, stop, step = sli.start, sli.stop, sli.step
    if stop is None:
        raise IndexError("An exact number must be provided for stop")
    return range(0 if start is None else start, stop, 1 if step is None else step)

_m_INDEX = int, cast(type, np.integer), str, tuple

CSelf = TypeVar('CSelf',  bound = 'TrackViewConfigMixin')
class TrackViewConfigMixin: # pylint: disable=invalid-name
    "Adds methods for configuring a TracksView"
    data:      TRACK_VIEW             = None
    selected:  List                   = None
    discarded: List                   = None
    beadsonly                         = False
    actions:   List                   = []
    parents:   Union[Tuple, Hashable] = tuple()
    _COPY:     bool                   = None
    def __init__(self, **kw) -> None:
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
            self.actions.append(lambda item: (item[0], item[1][samples]))

    copy = staticmethod(_m_copy)    # type: ignore

    @staticmethod
    def isbead(key) -> bool:
        "returns whether the key is one for a bead"
        return ((isinstance(key, tuple)
                 and len(key) > 0
                 and isinstance(key[0], _m_INTS)
                ) or isinstance(key,    _m_INTS))

    def withbeadsonly(self:CSelf, beadsonly = True) -> CSelf:
        "discards all but beads"
        self.beadsonly = beadsonly
        return self

    def withsamples(self:CSelf, samples) -> CSelf:
        "specifies that only some samples should be taken"
        if samples is not None:
            self.actions.append(lambda item: (item[0], item[1][samples]))
        return self

    def withcopy(self:CSelf, cpy:bool = True) -> CSelf:
        "specifies that a copy of the data should or shouldn't be made"
        fcn = getattr(self, 'copy', _m_copy)
        if cpy and fcn not in self.actions:
            self.actions.append(fcn)
        elif not cpy and fcn in self.actions:
            self.actions.remove(fcn)
        return self

    def withfunction(self:CSelf, fcn = None, clear = False, beadsonly = False) -> CSelf:
        "Adds an action with fcn taking a value as single argument"
        if clear:
            self.actions = []

        if fcn is None:
            return self

        _m_check_action_sig(fcn)
        if beadsonly:
            isbead = self.isbead
            @wraps(fcn)
            def _action(col):
                return col[0], (fcn(col[1]) if isbead(col[0]) else col[1])
            self.actions.append(_action)
        else:
            self.actions.append(lambda col: (col[0], fcn(col[1])))
        return self

    def withaction(self:CSelf, fcn = None, clear = False, beadsonly = False) -> CSelf:
        "Adds an action with fcn taking a (key, value) pair as single argument"
        if clear:
            self.actions = []

        if fcn is None:
            return self

        _m_check_action_sig(fcn)
        if beadsonly:
            isbead = self.isbead
            @wraps(fcn)
            def _action(col):
                return fcn(col) if isbead(col[0]) else col
            self.actions.append(_action)
        else:
            self.actions.append(fcn)
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
        if not isinstance(cyc, List) and cyc in _m_ALL:
            setattr(self, attr, None)
            return self

        if clear:
            setattr(self, attr, None)

        if getattr(self, attr) is None:
            setattr(self, attr, [])

        if isinstance(cyc, tuple):
            if all(isinstance(i, _m_INDEX) or _m_ellipsis(i) for i in cyc):
                getattr(self, attr).append(cyc)
            else:
                vals = ((i,)          if (isinstance(i, _m_INDEX) or _m_ellipsis(i)) else
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

    def getaction(self, actions = None):
        "returns a function performing all actions"
        if actions is None:
            actions = self.actions

        if len(actions) > 1:
            def _act(item):
                for action in actions:
                    item = action(item)
                return item
            return _act

        return actions[0] if len(actions) == 1 else None
