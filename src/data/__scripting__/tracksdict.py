#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds a dictionnaries to access tracks, experiments, ...
"""
import re
from   typing                       import List, FrozenSet, TypeVar, cast
from   functools                    import partial
import pandas                       as     pd
import numpy                        as     np

from   utils.decoration             import addto, addproperty
from   utils.attrdefaults           import setdefault, deepcopy
from   model                        import Task
from   model.__scripting__          import Tasks
from   model.__scripting__.parallel import Parallel
from   control.processor.dataframe  import SafeDataFrameProcessor
from   control.processor.base       import register

from   ..track                      import Track
from   ..views                      import BEADKEY
from   ..trackio                    import savetrack, PATHTYPE, Handler
from   ..trackops                   import clone
from   ..tracksdict                 import TracksDict as _TracksDict
from   ..views                      import isellipsis

@addto(Handler)
def __call__(self, track = None, beadsonly = False, __old__ = Handler.__call__) -> Track:
    if track is None:
        track = Track()
    return __old__(self, track, beadsonly)

class FrozenTrack(Track):
    "Track where the data is also part of the state"
    def __init__(self, track = None, **kwa):
        super().__init__(**kwa)
        if track:
            self.__dict__.update(track.__dict__)

    def __getstate__(self):
        self.load()
        state = super().__getstate__()
        state.update(data        = dict(self.data),
                     secondaries = dict(self.secondaries.data))
        return state

class TracksDict(_TracksDict):
    """
    ## Saving

    It's possible to save the tracks to a '.pk' which are much faster at
    loading. To save the files:

    ```python
    >>> tracks.save("/path/to/my/saved/tracks")
    ```

    The tracks are saved as "/path/to/my/saved/tracks/key.pk" files.
    Thus, loading them is as simple as:

    ```python
    >>> TRACKS = TracksDict("/path/to/my/saved/tracks/*.pk")
    ```
    """
    if __doc__:
        __doc__ = _TracksDict.__doc__ + __doc__
    _TRACK_TYPE = Track
    def __init__(self,          # pylint: disable=too-many-arguments
                 tracks  = None,
                 grs     = None,
                 match   = None,
                 allaxes = False,
                 tasks   = None,
                 cleaned = None,
                 **kwa):
        super().__init__(tracks, grs, match, allaxes, **kwa)
        if cleaned is not None:
            self.cleaned = cleaned
        self.tasks   = tasks

    def select(self, key):
        """
        selects tracks as follows:

        * `key == 'clean'` only cleaned tracks
        * `key == '~clean'` only uncleaned tracks
        * '3w1s': 4-mers with 3 weaks and 1 strong
        * '3w': 3-mers with 3 weaks
        * ...
        * normal regular expression: only tracks matching that expression
        """
        if not isinstance(key, str):
            return super().__getitem__([key])

        if key == 'clean':
            return super().__getitem__([i for i, j in self.items() if i.clean])

        if key == '~clean':
            return super().__getitem__([i for i, j in self.items() if not i.clean])

        try:
            if 'w' not in key.lower() and 's' not in key.lower():
                raise ValueError()
            int(key.lower().replace('w', '').replace('s', ''))
        except ValueError:
            reg = re.compile(key) if isinstance(key, str) else key
            return super().__getitem__([i for i in self if reg.match(i)])

        key = key.lower()
        if 'w' not in key:
            tot = int(key.replace('s', ''))
            cnt = [0, tot]

        elif 's' not in key:
            tot = int(key.replace('s', ''))
            cnt = [tot, 0]

        else:
            cnt = [int(i) for i in key.replace('s', 'w').split('w')]
            if key.index('s') < key.index('w'):
                cnt = cnt[::-1]

            tot = sum(cnt)

        fcn = lambda i: (len(i) == tot and
                         i.count('a') + i.count('t') == cnt[0] and
                         i.count('c') + i.count('g') == cnt[1])
        return super().__getitem__([i for i in self if fcn(i.lower())])

    def __getitem__(self, key):
        if isinstance(key, list) or isellipsis(key):
            return super().__getitem__(key)

        if isinstance(key, (Task, Tasks)):
            return self.apply(key)

        if isinstance(key, tuple) and all(isinstance(i, (Task, Tasks)) for i in key):
            return self.apply(*key)

        if (callable(getattr(key, 'match', None)) or
                (key in ('clean', '~clean') and key not in self)):
            return self.select(key)

        if key not in self and ('w' in key.lower() or 's' in key.lower()):
            try:
                int(key.lower().replace('w').replace('s'))
            except ValueError:
                pass
            else:
                return self.select(key)

        trk = super().__getitem__(key)
        return trk.apply(*self.tasks) if self.tasks else trk

    def apply(self, *tasks) -> 'TracksDict':
        "returns a new tracksdict with default tasks"
        other = type(self)(tasks = tasks)
        other.update(self)
        return other

    def save(self, path: PATHTYPE) -> 'TracksDict':
        "saves the data to a directory"
        if self.tasks:
            raise NotImplementedError("don't know how to save that")
        return savetrack(path, self)

    @property
    def cleaned(self):
        "wether all tracks are cleaned"
        return all(i.cleaned for i in self.values())

    @cleaned.setter
    def cleaned(self, value):
        """
        Sets tracks to cleaned.

        If provided with a string or a list, the corresponding tracks are defined
        as cleaned, the others as dirty.
        """
        if isinstance(value, (str, list)):
            self.cleaned        = False
            self[value].cleaned = True

        else:
            for i in self.values():
                i.cleaned = value

    def clone(self) -> 'TracksDict':
        "clone the tracks and return a new tracksdict"
        return cast(TracksDict, clone(self))

    def basedataframe(self, loadall = False) -> pd.DataFrame:
        "Returns a table with some data on the track files"
        if loadall:
            self.load()
        beads   = [sum(1 for i in j.beadsonly.keys()) if j.isloaded else np.NaN
                   for j in self.values()]
        cleaned = [i.cleaned if i.isloaded else np.NaN for i in self.values()]

        paths = [i.pathinfo for i in self.values()]
        frame = dict(key     = list(self),
                     path    = [i.trackpath for i in paths],
                     cleaned = cleaned,
                     beads   = beads,
                     **{i: [getattr(j, i) for j in paths]
                        for i in ('pathcount', 'modification', 'megabytes')})
        return pd.DataFrame(frame).sort_values('modification')

    def trackdataframe(self, *tasks,
                       transform = None,
                       assign    = None,
                       process   = True,
                       **kwa) -> pd.DataFrame:
        """
        Tasks are applied to each track, with the last one being a
        DataFrameTask constructed using all other keywords.

        **Warning:** the first task should be either event detection or peak
        selection.
        """
        try:
            Tasks(tasks[0])
        except (IndexError, ValueError) as _:
            raise ValueError('The first task should be either '
                             'event detection or peak selection.')

        transform = ([transform] if callable(transform) else
                     []          if transform is None   else
                     list(transform))
        if assign is not None:
            transform.insert(0, partial(pd.DataFrame.assign, **assign))

        if Tasks(tasks[-1]) is Tasks.dataframe:
            transform = tasks[-1].transform + transform
            tmp, kwa  = kwa, tasks[-1].measures
            kwa.update(tmp)
            tasks = tasks[:-1]

        dframe  = Tasks.dataframe(merge = True, measures = kwa, transform = transform)
        created = [Tasks.create(i) for i in tasks[1:]]
        procs   = register(SafeDataFrameProcessor, cache = register(), recursive = False)
        par     = Parallel()
        for j in self.values():
            par.extend([j], *Tasks.defaulttasklist(j, tasks[0], j.cleaned),
                       *created, dframe, processors = procs)
        return par.process(None, 'concat') if process else par

    def dataframe(self, *tasks,
                  loadall   = False,
                  transform = None,
                  assign    = None,
                  process   = True,
                  **kwa):
        "Returns either `basedataframe` or `trackdataframe`"
        if len(tasks) == 0:
            return self.basedataframe(loadall)
        kwa.update(transform = transform, assign = assign, process = process)
        return self.trackdataframe(*tasks, **kwa)

    def freeze(self) -> 'TracksDict':
        "Loads all tracks and adds the data to the track state"
        self.load()
        cpy = self.__class__()
        dict.update(cpy, {i: FrozenTrack(j) for i, j in self.items()})
        return cpy

    def changeattributes(self, *_, inplace = True, **kwa) -> 'TracksDict':
        """
        change attributes for all tracks
        """
        assert len(_) == 0
        this = self if inplace else self.clone()
        for track in this.values():
            for i, j in kwa.items():
                setattr(track, i, j)
        return this

    dataframe.__doc__ =(
        f"""
        Returns a dataframe which is either:

        ### Tasks are provided
        {trackdataframe.__doc__}

        ### Tasks not are provided
        {basedataframe.__doc__}
        """)

Self = TypeVar('Self', bound = 'TracksDictOperator')
class TracksDictOperator:
    """
    Allows applying operations to a specific portion of the tracksdict
    """
    _beads:     List[BEADKEY] = None
    _keys:      List[str]     = None
    _reference: str           = None
    _items:     TracksDict    = None
    KEYWORDS: FrozenSet[str] = frozenset(locals()) - {'_items'}
    def __init__(self, items, **opts):
        if all(hasattr(items, i) for i in ('_beads', '_keys', '_reference', '_items')):
            opts, kwa   = items.config(minimal = True), opts
            opts.update(kwa)
            items       = getattr(items, '_items')
        self._items   = items
        for i in self.KEYWORDS:
            if i[:2] != '__':
                setdefault(self, i[1:], opts, fieldname = i)

    def __init_subclass__(cls, **args):
        for name, itm in args.items():
            if isinstance(itm, tuple):
                addproperty(itm[0], name, cls, **itm[1])
            else:
                addproperty(itm, name, cls)

    def config(self, name = ..., minimal = False):
        "returns the config"
        if isinstance(name, str):
            return getattr(self, '_'+name)

        keys = {i for i in self.__dict__
                if (i != '_items' and
                    len(i) > 2 and i[0] == '_'   and
                    i[1].lower() == i[1])}
        if minimal:
            keys -= {i for i in keys if getattr(self, i) == getattr(self.__class__, i)}

        return {i[1:]: deepcopy(getattr(self, i)) for i in keys}

    def __call__(self: Self, **opts) -> Self:
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
            self._keys  = None
            self._beads = None

        elif values in self._items:
            self._keys  = [values]
        else:
            raise KeyError("Could not slice the operator")
        return self

__all__ = ['TracksDict']
