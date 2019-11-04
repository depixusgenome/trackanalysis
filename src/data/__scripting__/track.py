#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track class.

We add some methods and change the default behaviour:

* *__init__* takes *path* as it's first positional argument
* an *events* property is added
"""
from   copy                 import copy  as shallowcopy, deepcopy
from   functools            import partial
from   typing               import cast

import numpy                as     np

from   taskmodel               import PHASE, Task
from   taskmodel.__scripting__ import Tasks
from   utils.decoration        import addproperty, extend
from   utils.attrdefaults      import addattributes

from   ..trackio               import savetrack
from   ..views                 import TrackView, Cycles, Beads
from   ..track                 import Track, LazyProperty, isellipsis
from   ..trackops              import (selectbeads, dropbeads, selectcycles,
                                       concatenatetracks, renamebeads, clone,
                                       dataframe)
from   .tracksdict             import TracksDict

@addproperty(Track, 'op')
class TrackOperations:
    """
    A number of helper functions for selecting/discarding beads and cycles or
    concatenating files:

        * `track.op.save("path")` saves the track
        * `track.op.concatenate(track2, track3)` concatenates 3 experiments
        * `track.op + track2` concatenates 2 experiments
        * `del track.op[[1,3]]` deletes beads 1 and 3
        * `track.op.beads[[1,3]]` returns track with only beads 1 and 3
        * `track.op.beads[[1,3], [1,5]]` returns track with only beads 1 and 3, cycles 1 and 5
        * `track.op.beads[:, 1:5]` returns track with all beads 1 and cycles 1 to 5
    """
    def __init__(self, trk):
        self._trk = trk

    class _Add:
        def __init__(self, fcn):
            self._fcn    = fcn
            self.__doc__ = fcn.__doc__

        def __get__(self, instance, owner):
            if instance is None:
                return self._fcn
            return partial(self._fcn, getattr(instance, '_trk'))

    concatenate  = _Add(concatenatetracks)
    save         = _Add(savetrack)
    rename       = _Add(renamebeads)
    clone        = _Add(clone)

    def __add__(self, other):
        return self.concatenate(getattr(other, '_trk', other))

    def drop(self, *beads: int) -> Track:
        """
        Drops beads
        """
        return self.__delitem__(list(beads))

    def __delitem__(self, beads) -> Track:
        if isinstance(beads, list):
            return dropbeads(self._trk, *beads)
        if np.isscalar(beads):
            return dropbeads(self._trk, beads)
        raise NotImplementedError()

    def __getitem__(self, beads) -> Track:
        if isinstance(beads, list):
            return selectbeads(self._trk, *beads)

        if np.isscalar(beads):
            return selectbeads(self._trk, beads)

        if isinstance(beads, tuple):
            if len(beads) != 2:
                raise KeyError("Key should be a (beads, cycles) tuple")
            trk = self._trk if isellipsis(beads[0]) else self.__getitem__(beads[0])
            trk = trk      if isellipsis(beads[1]) else selectcycles(trk, beads[1])
            return shallowcopy(self._trk) if trk is self._trk else trk
        raise NotImplementedError()

    def select(self, beads = None, cycles = None) -> Track:
        """
        Selects beads and cycles
        """
        return self.__getitem__((beads, cycles))

    def __setitem__(self, key: int, val: int) -> Track:
        if isinstance(key, (list, tuple)):
            return renamebeads(self._trk, *zip(key, val))
        return renamebeads(self._trk, (key, val))

    def rescaletobead(self, bead) -> Track:
        "rescales elements to the current bead"
        self._trk.load()
        trk   = shallowcopy(self._trk)
        items = getattr(Tasks.tasksmodel(), 'rescale')(trk, bead)
        instr = trk.instrument['type'].value
        if instr in items:
            names = {j: i for i, j in getattr(Tasks, '_cnv')(None).items()}
            for i, j in items[instr].items():
                if j.zscaledattributes() == ():
                    continue
                if hasattr(trk.tasks, names.get(i, i)):
                    setattr(trk.tasks, names.get(i, i), j)
            trk.instrument['rescaling'] = items['rescaling'][instr]
        else:
            trk.instrument.pop('rescaling', None)
        return trk

class CleanedProperty(LazyProperty):
    "Checks whether the file was opened prior to returning a value"
    def _load(self, inst):
        if inst.isloaded:
            return

        if isinstance(inst.path, (tuple, list)) and len(inst.path) > 1:
            inst.load()
        else:
            setattr(inst, self._name, False)

@extend(Track)
class _TrackMixin:
    "Additional track methods"
    if __doc__:
        __doc__  = '    * `op` a'          + cast(str, TrackOperations.__doc__)[6:]

    cleaned = CleanedProperty()

    def tasklist(self, *args):
        "creates a tasklist"
        return Tasks.tasklist(self.path, *args)

    def processors(self, *args, copy = True):
        "returns an iterator over the result of provided tasks"
        procs = Tasks.processors(self, *args)
        procs.data.setcachedefault(0, self)
        procs.copy = copy
        return procs

    def apply(self, *args, copy = True) -> TrackView:
        """
        Return an iterator over the result of provided tasks.

        The first argument can be an Ellipsis in which case:

        * the second argument must be any task from `Tasks.__tasklist__`,
        * tasks from `Tasks.defaulttasklist` will be inserted in front of the latter.

        This behaviour is most similar to what is obtained using shortcuts such as
        `track.cleancycles`.

        If no Ellipsis is introduced, the list of tasks is completed using the reduced
        list in `Tasks.defaulttaskorder`. This list does not include any cleaning task.
        """
        args  = deepcopy(args)
        procs = self.processors(*args)
        itr   = next(iter(procs.run(copy = copy)))
        assert not hasattr(itr, 'tasklist')
        setattr(itr, 'tasklist', procs.model)
        return itr

    @property
    def cleanbeads(self) -> Beads:
        "Return cleaned beads"
        return cast(Beads, self.apply(*Tasks.defaulttasklist(self, Tasks.alignment)))

    @property
    def cleancycles(self) -> Cycles:
        "Return cleaned cycles"
        beads = self.cleanbeads
        out   = cast(Cycles, beads[...,...])
        assert not hasattr(out, 'tasklist')
        setattr(out, 'tasklist', getattr(beads, 'tasklist'))
        return out

    @property
    def measures(self):
        "Return cleaned cycles for `PHASE.measure` only"
        return self.cleancycles.withphases(PHASE.measure)

    for prop in cleanbeads, cleancycles, measures:
        setattr(prop, '__doc__', getattr(prop, '__doc__') + f"\n{Tasks.__cleaning__.__doc__}")
        del prop

    def astracksdict(self, *beads:int) -> TracksDict:
        """
        Converts this to a `TracksDict` object, with one bead per track.

        This can be used to work across beads in a track as one would accross
        tracks in a `TracksDict`.
        """
        if len(beads) == 1 and isinstance(beads[0], (tuple, list, set, frozenset)):
            beads = tuple(beads[0])
        if len(beads) == 0:
            beads = tuple(self.beads.keys()) # type: ignore
        fcn = lambda i: renamebeads(selectbeads(cast(self, Task), i), (i, 0)) # type: ignore
        return TracksDict({i: fcn(i) for i in beads})

    dataframe = dataframe

    def __getitem__(self, value):
        if isinstance(value, (Task, Tasks)):
            value = (value,)

        if isinstance(value, range):
            value = set(value) & set(self.data.keys())

        if isinstance(value, (list, set, tuple, frozenset)):
            if all(isinstance(i, (Task, Tasks)) for i in value):
                return self.apply(*value)
            if '~' in value:
                return dropbeads(self, *(i for i in value if i != '~'))

        return selectbeads(self, value)


addattributes(Track, protected = dict(cleaned = False))
Track.cycles.args['copy'] = True
Track.beads .args['copy'] = True

__all__ = ['Track']
