#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds methods for configuring a TracksView"
from   inspect          import signature
from   copy             import copy as shallowcopy, deepcopy
from   itertools        import product
from   functools        import partial
from   typing           import (Tuple, Iterable, Union, List, TypeVar, Hashable,
                                Callable, Optional, cast)
import numpy            as     np

from   utils            import isfunction
from   ._dict           import TRACK_VIEW, TransformedTrackView, isint, isellipsis

def _m_copy(_, item):
    "Copies the data"
    return (item[0],
            np.copy(item[1]) if isinstance(item[1], np.ndarray) else deepcopy(item[1]))

def _m_torange(sli):
    start, stop, step = sli.start, sli.stop, sli.step
    if stop is None:
        raise IndexError("An exact number must be provided for stop")
    return range(0 if start is None else start, stop, 1 if step is None else step)

_m_INDEX = int, cast(type, np.integer), str, tuple

CSelf = TypeVar('CSelf',  bound = 'TrackViewConfigMixin')
class TrackViewConfigMixin(Iterable): # pylint: disable=invalid-name,inherit-non-class
    """
    This object provides a view on all {views} as well as *time* and *magnet altitude*.
    {datadescr}

    ```python{itercode}
    ```

    ### Configuration Methods
    {selecting}

    * `discarding` works as for `selecting`

    * `withaction` allows applying a number of transformations to the data. The
    user must provide a function taking the `Cycles` object as first argument
    and a tuple `(id, data)`. To multiply the data by 1.5, do (one could use a
    lambda function):

    ```python{actioncode}
    ```

    * `withsamples` takes a `slice` instance as argument and applies it to the data.
    To select 1 out of 2 points, do: `track.{views}.withsamples(slice(None, None, 2))

    * `withcycles` takes a `slice` instance as argument and discards cycles which
    with ids outside that slice.

    * `withcopy` takes a boolean as argument and  will make a copy of the data
    before passing it on. This is the default configuration.

    * `withdata` allows setting data on which to iterate. To be used sparingly.

    *Note* that all methods return the same object which means that they can
    be chained together. For example:

    ```python{chaincode}
    ```
    """
    data:      Optional[TRACK_VIEW]   = None
    selected:  Optional[List]         = None
    discarded: Optional[List]         = None
    actions:   List[Callable]         = []
    parents:   Union[Tuple, Hashable] = tuple()
    _COPY:     Optional[bool]         = None
    def __init__(self, **kw) -> None:
        super().__init__()
        get = lambda x: kw.get(x, shallowcopy(getattr(self.__class__, x)))
        self.data      = get('data')
        self.parents   = get('parents')
        self.actions   = get('actions')

        self.__selection('selected',  get('selected'),  False)
        self.__selection('discarded', get('discarded'), False)

        if kw.get('copy', self._COPY):
            self.actions.append(getattr(self, 'copy', _m_copy))

        if kw.get('samples', None) is not None:
            samples = kw['samples']
            self.actions.append(partial(self._f_samples, samples))

    @staticmethod
    def __format_doc__(more, **kwa):
        doc   = TrackViewConfigMixin.__doc__
        if doc:
            eight = '\n        ', '\n    '
            return doc.format(**{i: j.replace(*eight) for i, j in kwa.items()}) + more
        return None

    copy = staticmethod(_m_copy)    # type: ignore

    @staticmethod
    def isbead(key) -> bool:
        "returns whether the key is one for a bead"
        return ((isinstance(key, tuple)
                 and len(key) > 0
                 and isint(key[0])
                ) or isint(key))

    @staticmethod
    def _f_samples(samples, _, info):
        return info[0], info[1][samples]

    def withsamples(self:CSelf, samples) -> CSelf:
        "specifies that only some samples should be taken"
        if samples is not None:
            if isinstance(samples, range):
                samples = slice(samples.start, samples.stop, samples.step) # type: ignore
            self.actions.append(partial(self._f_samples, samples))
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
    def _f_all(_, fcn, items):
        return items[0], fcn(items[1])

    def withfunction(self:CSelf, fcn = None, clear = False) -> CSelf:
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

        self.actions.append(partial(self._f_all, fcn))
        return self

    def withaction(self:CSelf, fcn = None, clear = False) -> CSelf:
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
