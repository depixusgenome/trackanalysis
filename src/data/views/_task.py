#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Makes TrackViews for specific tasks easier"
from typing import (Generic, TypeVar, Type, Union, Optional,
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
        if sel is None:
            sel = self.selected
        if isinstance(self.data, self.__class__):
            data = cast(TrackView, self.data)
            yield from ((key, data.get(key)) for key in self.keys(sel))
        else:
            fcn = self._get_iter_function()
            yield from ((key, fcn(key)) for key in self.keys(sel))

    def _get_iter_function(self):
        return self.compute

    def _get_data_keys(self):
        return self.data.keys()

    def _keys(self, sel:Optional[Sequence[Key]], beadsonly: bool) -> Iterable[Key]:
        if self.__keys is None:
            self.__keys = frozenset(self._get_data_keys())

        if sel is None:
            yield from self.__keys
        else:
            good = self._transform_ids(cast(Iterable, sel))
            yield from (i for i in good if i in self.__keys)

    @staticmethod
    def _transform_ids(sel: Iterable) -> Iterator[Key]:
        return cast(Iterator[Key], iter(sel))

    @abstractmethod
    def compute(self, key: Key):
        "computes results for one key"
