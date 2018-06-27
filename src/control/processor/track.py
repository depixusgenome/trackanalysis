#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from    copy             import deepcopy
from    functools        import partial
from    typing           import TYPE_CHECKING, Iterable, Union, Sequence, cast

import  model.task.track as     _tasks
from    model.level      import Level
from    data.track       import Track
from    data.trackops    import selectcycles
from    data.tracksdict  import TracksDict
from    .base            import Processor

if TYPE_CHECKING:
    from .runner    import Runner # pylint: disable=unused-import

class InMemoryTrackProcessor(Processor[_tasks.InMemoryTrackTask]):
    "Generates output from a _tasks.InMemoryTrackProcessor"
    def run(self, args:'Runner'):
        "updates frames"
        task = cast(_tasks.InMemoryTrackTask, self.task)
        trk  = args.data.setCacheDefault(self, deepcopy(task.track))
        args.apply((trk.beads,), levels = self.levels)

    @staticmethod
    def beads(cache, selected: Iterable[int]) -> Iterable[int]: # pylint: disable=unused-argument
        "Beads selected/discarded by the task"
        return cache.beads.keys()

class TrackReaderProcessor(Processor[_tasks.TrackReaderTask]):
    "Generates output from a _tasks.CycleCreatorTask"
    @classmethod
    def __get(cls, attr, cpy, trk):
        vals = (trk,) if isinstance(trk, Track) else trk.values()
        return tuple(getattr(i, attr).withcopy(cpy) for i in vals)

    def run(self, args:'Runner'):
        "updates frames"
        task  = cast(_tasks.TrackReaderTask, self.task)
        attr  = 'cycles' if task.levelou is Level.cycle else 'beads'
        if isinstance(task.path, dict):
            trk = args.data.setCacheDefault(self, TracksDict())
            trk.update(task.path)
        else:
            trk = args.data.setCacheDefault(self,
                                            Track(path = task.path,
                                                  key  = task.key,
                                                  axis = task.axis))
            args.apply(self.__get(attr, task.copy, trk), levels = self.levels)

    @staticmethod
    def beads(cache, selected: Iterable[int]) -> Iterable[int]: # pylint: disable=unused-argument
        "Beads selected/discarded by the task"
        return cache.beads.keys()

class CycleCreatorProcessor(Processor[_tasks.CycleCreatorTask]):
    "Generates output from a _tasks.CycleCreatorTask"
    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        fcn = lambda data: data[...,...].withphases(kwa['first'], kwa['last'])
        return fcn if toframe is None else fcn(toframe)

    def run(self, args:'Runner'):
        "iterates through beads and yields cycles"
        args.apply(self.apply(**self.config()), levels = self.levels)

class CycleSamplingProcessor(Processor[_tasks.CycleSamplingTask]):
    "Generates output from a _tasks.CycleSamplingTask"
    @classmethod
    def apply(cls, toframe = None, cycles: Union[Sequence[int], slice] = None):
        "applies the task to a frame or returns a function that does so"
        if toframe is None:
            return partial(cls.apply, cycles = cycles)
        return toframe.withdata(partial(selectcycles, toframe.track, cycles))

    def run(self, args:'Runner'):
        "iterates through beads and yields cycles"
        args.apply(self.apply(**self.config()))

class DataSelectionProcessor(Processor[_tasks.DataSelectionTask]):
    "Generates output from a DataSelectionTask"
    @staticmethod
    def __apply(kwa, frame):
        for name, value in kwa.items():
            getattr(frame, name)(value)
        return frame

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        names = lambda i: ('selecting'  if i == 'selected'  else
                           'discarding' if i == 'discarded' else
                           'with'+i)

        kwa   = {names(i): j for i, j in kwa.items()
                 if j is not None and i not in ('level', 'disabled')}

        return partial(cls.__apply, kwa) if toframe is None else cls.__apply(kwa, toframe)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

    def beads(self, _, selected: Iterable[int]) -> Iterable[int]: # type: ignore
        "Beads selected/discarded by the task"
        task = cast(_tasks.DataSelectionTask, self.task)
        if task.selected and task.discarded:
            acc       = frozenset(task.selected) - frozenset(task.discarded)
            selected  = iter(i for i in selected if i in acc)
        elif task.selected:
            acc       = frozenset(task.selected)
            selected  = iter(i for i in selected if i in acc)
        elif task.discarded:
            disc      = frozenset(task.discarded)
            selected  = iter(i for i in selected if i not in disc)
        return selected
