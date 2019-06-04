#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
from typing  import Any, Union, Tuple, Optional, Dict, TypeVar, TYPE_CHECKING
from abc     import ABC, abstractmethod
from pathlib import Path

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.track      import Track
    from data.tracksdict import TracksDict
    DictType = TypeVar('DictType', bound = 'TracksDict')
else:
    DictType = 'TracksDict'
    Track    = 'Track'

PATHTYPE  = Union[str, Path]
PATHTYPES = Union[PATHTYPE,Tuple[PATHTYPE,...]]

def globfiles(path:str):
    "obtain all files"
    ind1 = path.find('*')
    ind2 = path.find('[')
    ind  = ind1 if ind2 == -1 else ind2 if ind1 == -1 else min(ind1, ind2)
    if ind == -1:
        return Path(path)

    root = Path(path[:ind])
    if path[ind-1] not in ('/', '\\') and root != Path(path).parent:
        return Path(str(root.parent)).glob(root.name+path[ind:])
    return Path(root).glob(path[ind:])

class TrackIO(ABC):
    "interface class for Track IO"
    PRIORITY = 1000
    @classmethod
    @abstractmethod
    def check(cls, path:PATHTYPES, **_) -> Optional[PATHTYPES]:
        "checks the existence of a path"

    @staticmethod
    def checkpath(path:PATHTYPES, ext:str) -> Optional[PATHTYPES]:
        "checks the existence of a path"
        if isinstance(path, (tuple, list, set, frozenset)) and len(path) == 1:
            path = path[0]
        if isinstance(path, (str, Path)):
            return path if Path(path).suffix == ext else None
        return None

    @classmethod
    @abstractmethod
    def open(cls, path:PATHTYPE, **_) -> Dict[Union[str, int], Any]:
        "opens a track file"

    @staticmethod
    @abstractmethod
    def instrumenttype(path:str) -> str:
        "return the instrument type"
