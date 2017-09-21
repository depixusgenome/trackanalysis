#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Makes TrackViews for specific tasks easier"
from typing import (Generic, TypeVar, Type, Union,
                    Iterable, Sequence, Iterator, FrozenSet, cast)
from abc    import abstractmethod
from ._view import TrackView

Config = TypeVar('Config')
Key    = TypeVar('Key')

class TaskView(TrackView, Generic[Config, Key]):
    "iterator over peaks grouped by beads"
    def __init__(self, *_, config: Union[Config, dict] = None, **kwa) -> None:
        assert len(_) == 0
        super().__init__(**kwa)
        ctype = self.tasktype()
        cnf   = (ctype()         if config is None            else
                 ctype(**config) if isinstance(config, dict)  else # type: ignore
                 config          if isinstance(config, ctype) else
                 None)
        if cnf is None:
            raise ValueError(f"Could not initialize {self.__class__}")

        self.config: Config         = cast(Config, cnf)
        self.__keys: FrozenSet[Key] = None

    @classmethod
    def tasktype(cls) -> Type[Config]:
        "returns the config type"
        return cls.__orig_bases__[0].__args__[0] # type: ignore

    def _iter(self, sel:Sequence = None) -> Iterator:
        if isinstance(self.data, self.__class__):
            itr = iter(cast(Iterable, self.data))
            if sel is None:
                yield from itr
            else:
                yield from ((i, j) for i, j in itr if i in sel)
        yield from ((key, self.compute(key)) for key in self.keys(sel))

    def _keys(self, sel:Sequence = None, _ = None) -> Iterator[Key]:
        if self.__keys is None:
            self.__keys = frozenset(self.data.keys())

        if sel is None:
            yield from self.__keys
        else:
            yield from (i for i in self.__keys if i in sel)

    @abstractmethod
    def compute(self, key: Key):
        "computes results for one key"
