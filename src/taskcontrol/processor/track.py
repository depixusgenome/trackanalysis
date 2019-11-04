#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from    copy             import deepcopy
from    functools        import partial
from    typing           import (
    TYPE_CHECKING, Iterable, Union, Sequence, Dict, Any, cast
)

import  numpy            as     np

from    data.track       import Track, Beads
from    data.trackops    import selectcycles, undersample
from    data.tracksdict  import TracksDict
import  taskmodel.track  as     _tasks
from    taskmodel        import Level
from    .base            import Processor

if TYPE_CHECKING:
    from .runner    import Runner  # pylint: disable=unused-import

class InMemoryTrackProcessor(Processor[_tasks.InMemoryTrackTask]):
    "Generates output from a _tasks.InMemoryTrackProcessor"
    def run(self, args:'Runner'):
        "updates frames"
        task = cast(_tasks.InMemoryTrackTask, self.task)
        trk  = args.data.setcachedefault(self, deepcopy(task.track))
        args.apply((trk.beads,), levels = self.levels)

    @staticmethod
    def beads(cache, selected: Iterable[int]) -> Iterable[int]:  # pylint: disable=unused-argument
        "Beads selected/discarded by the task"
        return cache.beads.keys()

class TrackReaderProcessor(Processor[_tasks.TrackReaderTask]):
    "Generates output from a _tasks.CycleCreatorTask"
    @classmethod
    def __get(cls, attr, cpy, trk, und):

        def _open(trk):
            if und is not None:
                trk.load(und.cycles)
            return getattr(trk, attr).withcopy(cpy, 0)

        vals = (trk,) if isinstance(trk, Track) else trk.values()
        return tuple(_open(i) for i in vals)

    def run(self, args:'Runner'):
        "updates frames"
        task   = cast(_tasks.TrackReaderTask, self.task)
        attr   = 'cycles' if task.levelou is Level.cycle else 'beads'
        rpcomp = next(
            (i for i in args.data.model if isinstance(i, _tasks.RawPrecisionTask)),
            _tasks.RawPrecisionTask
        ).computer
        if isinstance(task.path, dict):
            trk = args.data.setcachedefault(self, TracksDict())
            trk.update(task.path)
        else:
            trk = args.data.setcachedefault(
                self,
                Track(
                    path          = task.path,
                    key           = task.key,
                    axis          = task.axis,
                    rawprecisions = rpcomp
                )
            )

        und = next(
            (i for i in args.data.model if isinstance(i, _tasks.UndersamplingTask)),
            None
        )
        args.apply(self.__get(attr, task.copy, trk, und), levels = self.levels)

    @staticmethod
    def beads(cache, selected: Iterable[int]) -> Iterable[int]:  # pylint: disable=unused-argument
        "Beads selected/discarded by the task"
        return cache.beads.keys()

class UndersamplingProcessor(Processor[_tasks.UndersamplingTask]):
    """
    Resample the track
    """
    @staticmethod
    def binwidth(
            task: _tasks.UndersamplingTask,
            itm: Union[Track, Beads, float, int]
    ) -> int:
        "the number of old frames per new frame"
        old: float = (
            itm.framerate       if isinstance(itm, Track) else
            itm.track.framerate if isinstance(itm, Beads) else
            itm
        )
        cnt: int   = max(1, int(np.floor(old/task.framerate)))
        if abs(old/cnt-task.framerate) > abs(old/(cnt+1)-task.framerate):
            return cnt+1
        return cnt

    @classmethod
    def apply(cls, task: _tasks.UndersamplingTask, itm: Beads) -> Beads:
        "create a new track"
        width = cls.binwidth(task, itm)
        return undersample(itm, width, task.aggregation, task.cycles).beads

    def track(self, itm: Track) -> Track:
        "create a new track"
        width = self.binwidth(self.task, itm)
        return undersample(itm, width, self.task.aggregation, self.task.cycles)

    def run(self, args):
        "updates frames"
        args.apply(partial(self._apply, self.config()), levels = self.levels)

    @classmethod
    def _apply(cls, kwa: Dict[str, Any], beads:Beads):
        return cls.apply(_tasks.UndersamplingTask(**kwa), beads.track)

class RawPrecisionProcessor(Processor[_tasks.RawPrecisionTask]):
    """
    Resample the track
    """

    @classmethod
    def apply(cls, tpe: str, itm: Beads) -> Beads:
        "create a new track"
        if itm.track.rawprecision() == tpe:
            return itm

        itm.track = itm.track.shallowcopy()
        itm.track.rawprecision(tpe)
        return itm

    def run(self, args):
        "updates frames"
        args.apply(partial(self.apply, self.task.computer), levels = self.levels)

class CycleCreatorProcessor(Processor[_tasks.CycleCreatorTask]):
    "Generates output from a _tasks.CycleCreatorTask"
    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        fcn = lambda data: data[...,...].withphases(kwa['first'], kwa['last'])  # noqa
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
        names = lambda i: ('selecting'  if i == 'selected'  else  # noqa
                           'discarding' if i == 'discarded' else
                           'with'+i)

        kwa   = {names(i): j for i, j in kwa.items()
                 if j is not None and i not in ('level', 'disabled')}

        return partial(cls.__apply, kwa) if toframe is None else cls.__apply(kwa, toframe)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

    def beads(self, _, selected: Iterable[int]) -> Iterable[int]:  # type: ignore
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
