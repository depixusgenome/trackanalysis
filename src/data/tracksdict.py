#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds a dictionnaries to access tracks, experiments, ...
"""
from typing             import (KeysView, List, Dict, Any, # pylint: disable=unused-import
                                Iterator, Tuple, TypeVar, Union, Set, Optional,
                                Sequence, cast)
from pathlib            import Path
from anastore           import LocalPatch
from concurrent.futures import ThreadPoolExecutor
from copy               import copy as shallowcopy
import re

from .views   import isellipsis, BEADKEY
from .track   import Track
from .trackio import LegacyGRFilesIO, LegacyTrackIO, PATHTYPES

TDictType = TypeVar('TDictType', bound = 'TracksDict')
TrackType = TypeVar('TrackType', bound = 'Track')
def _leastcommonkeys(itr):
    info = dict(itr)
    keys = {i: i.split('_') for i in info.keys()}
    common = None
    for i in keys.values():
        common = set(i) if common is None else set(i) & common
    keys = {i:'_'.join(k for k in j if k not in common) for i, j in keys.items()}
    if '' in keys.values():
        keys[next(i for i, j in keys.items() if j == '')] = 'ref'
    return {keys[i]: j for i, j in info.items()}

class TracksDict(dict):
    """
    This a dictionnary of tracks. It provides *lazy* access to tracks as well
    as various methods for studying tracks together.

    ## Initialisation

    It can be initialized using list of directories

    ```python
    >>> TRACKS = TracksDict("/media/data/helicon/X/*/*.trk", # the path to .trk files
    ...                     "~/Seafile/X/*.cgr",             # Optional: the path to .cgr files
    ...                     #
    ...                     # Optional: We accept only files with _040_ in the name
    ...                     # and we take the following 3 letters as the track key
    ...                     match   = r".*_040_(\\w\\w\\w)_.*")
    ```

    We can now access the tracks as: `TRACKS['AAG']`, supposing the *AAG* oligo
    was tested.

    It's also possible to add specific tracks by providing a `Track` object, a
    string or a list of strings:

    ```python
    >>> TRACKS['specific'] = "/path/to/specific/track/file.trk"
    ```

    ### Optional arguments:

    * if `allleaves = True`, the parent directory containing the
    gr-files is used for pairing gr and trk files.
    * if `match = r".*_040_(\\w\\w\\w)_.*"` is used (or any other regular
    expression), only *track* file names matching the expression are accepted.
    There must be one group (the parentheses) which will be used as the access
    key. By default the track file name is used as a key.

    ## Shortcuts

    `TracksDict.commonbeads` returns the beads in common to all tracks in
    the `TracksDict` or to those tracks provided as arguments.

    `TracksDict.commonkeys` returns the tracks in common to all beads in
    the `TracksDict` or to those beads provided as arguments.

    ## Slicing

    Providing a list of keys as argument creates a new `TracksDict` containing
    only those keys. The same `Track` objects are used.

    ```python
    >>> dico = TracksDict()
    >>> dico.update(A = "a.trk", B = "b.trk", C = "c.trk")
    >>> assert dico['A'].path == "a.trk"
    ```

    ```python
    >>> fraction = dico[['A']]
    >>> assert isinstance(fraction, TracksDict)
    >>> assert set(fraction.keys()) == {'A'}
    >>> assert fraction['A'] is dico['A']
    ```

    Should a key start with with "~" (or should "~" appear in a list) then a
    TracksDict object is created containing all but that key:

    ```python
    >>> assert set(dico['~A'].keys()) == {'B', 'C'}
    >>> assert set(dico[['~', 'B', 'C'].keys()) == {'A'}
    ```
    """
    _SCAN_OPTS  = ('cgrdir', 'allleaves')
    _NTHREADS   = None
    _TRACK_TYPE = Track
    def __init__(self,          # pylint: disable=too-many-arguments
                 tracks  = None,
                 grs     = None,
                 match   = None,
                 allaxes = False,
                 **kwa):
        super().__init__()
        self.update(tracks = tracks, grs = grs, match = match, allaxes = allaxes, **kwa)

    @classmethod
    def _newtrack(cls, **kwa):
        return cls._TRACK_TYPE(**kwa)

    def _set(self, key, val, allaxes = False):
        # pylint: disable=unidiomatic-typecheck
        if type(val) is self._TRACK_TYPE and not allaxes:
            super().__setitem__(key, val)
            return None

        if isinstance(val, (tuple, list, set)) and len(val) == 1:
            val = str(next(iter(val)))

        if isinstance(val, (tuple, list, set)):
            state = dict(path = [str(i) for i in val]) # type: Dict[str, Any]
        elif isinstance(val, (str, Path)):
            state = dict(path = str(val))
        elif isinstance(val, dict):
            state = val
        elif isinstance(val, Track):
            state = val.__getstate__()
        else:
            raise NotImplementedError()

        for i in 'XYZ' if allaxes else 'Z':
            state['axis'] = i
            state['key']  = f'{i if i != "Z" else ""}{key}'
            super().__setitem__(state['key'], self._newtrack(**state))

        return val

    def __setitem__(self, key, val):
        return self._set(key, val)

    def __getitem__(self: TDictType, # pylint: disable=function-redefined
                    key: Union[List,Any]
                   ) -> Union[TDictType, TrackType]:
        if isellipsis(key):
            return shallowcopy(self)

        if isinstance(key, str) and len(key) and key[0] == '~' and key not in self:
            key = ['~', key[1:]]

        if isinstance(key, list):
            other = shallowcopy(self)
            bad   = set(key) - {'~'} if '~' in key else set(other)-set(key)
            for i in bad:
                other.pop(i)
            return other

        return super().__getitem__(key)

    scangrs = staticmethod(LegacyGRFilesIO.scangrs)
    scantrk = staticmethod(LegacyGRFilesIO.scantrk)

    def scan(self, # pylint: disable=too-many-arguments,too-many-locals
             tracks  : Union[str, Sequence[str]],
             grs     : Union[None, str, Sequence[str]] = None,
             cgrdir  : Union[str, Sequence[str]]       = "cgr_dir",
             match   : str                             = None,
             allaxes   = False,
             allleaves = False,
             **opts) -> KeysView[str]:
        r"""
        scans for trks and, if requested, gr files.

        ## Scanning for tracks only

        Simply disregard the `grs`, `cgrdir` and `allleaves` keywords.

        ## Matching tracks and gr files using cgr names

        By default, what is scanned for is not gr files but cgr files. These should
        bear the same name as track files. For example:

            /data/sirius/toto/my_track_name.trk

        matches

            /home/toto/Seafile/my_project/analyzed/cgr_dir/my_track_name.cgr

        The scan could then be configured as:

        ```python
        >>> tracks = TracksDict().scan("/data/sirius/**/*.trk",
        ...                            "/home/toto/Seafile/my_project/",
        ...                            cgrdir = 'cgr_dir')
        ```

        Note that `cgrdir` can be a list of potential parent directory names containing
        the cgr files.

        Another option is to provide a regular expression finishing in .cgr. In
        such a case the `cgrdir` keyword is discarded:

        ```python
        >>> tracks = TracksDict().scan("/data/sirius/**/*.trk",
        ...                            "/home/toto/Seafile/my_project/**/*.cgr")
        ```

        ## Matching tracks and gr files using directory names:

        Should one set `allleaves = True`, then cgr files are disregarded. The parent
        directory of gr files should then be that of the track file. For example:

            /data/sirius/toto/my_track_name.trk

        matches

            /home/toto/Seafile/my_project/analyzed/my_track_name/*.gr

        The scan could then be configured as:

        ```python
        >>> tracks = TracksDict().scan("/data/sirius/**/*.trk",
        ...                            "/home/toto/Seafile/my_project/",
        ...                            allleaves = True)
        ```

        When using `allleaves`, the `cgrdir` keyword is discarded.

        ## Finding keys: using the `match` keyword

        By default the track file name is used as the dictionnary key. It's possible
        to extract a shorter key from the filename using a regular expression:

        Consider files:

            /data/sirius/toto/test_040_FOV1_AAG_toto.trk
            /home/toto/Seafile/my_project/analyzed/test_040_FOV1_AAG_toto/bead1.gr

        and:

            /data/sirius/toto/test_500_FOV2_CCC_toto.trk
            /home/toto/Seafile/my_project/analyzed/test_500_FOV2_CCC_toto/bead1.gr

        The following will find the first track and not the second. It will also
        select 'AAG' as the key:

        ```python
        >>> tracks = TracksDict().scan("/data/sirius/**/*.trk",
        ...                            "/home/toto/Seafile/my_project/",
        ...                            allleaves = True,
        ...                            match     = r'.*_040_FOV*_(\w\w\w)_.*')
        ```

        The extracted key is always the 1st group (the parentheses). Please
        read the `re` module documentation for more information on regular
        expressions.
        """
        opts['cgrdir']    = cgrdir
        opts['allleaves'] = allleaves
        if isinstance(match, str) or hasattr(match, 'match'):
            grp = True
            tmp = re.compile(match) if isinstance(match, str) else match
            fcn = lambda i: tmp.match(str(i if isinstance(i, (str, Path)) else i[0]))
        else:
            grp = False
            fcn = lambda i: (Path(str(i if isinstance(i, (str, Path)) else i[0])).stem
                             if match is None else match)

        if not grs:
            itr = cast(Iterator[Tuple[Any, PATHTYPES]],
                       ((fcn((i,)), i) for i in LegacyTrackIO.scan(tracks)))
        else:
            itr = ((fcn(i), i) for i in LegacyGRFilesIO.scan(tracks, grs, **opts)[0])

        if grp:
            info = dict((i.group(1), j) for i, j in itr if i)
        else:
            info = _leastcommonkeys(itr)

        for i, j in info.items():
            self._set(i, j, allaxes)
        return info.keys()

    def update(self, *args,
               tracks  : Union[None, str, Sequence[str]] = None,
               grs     : Union[None, str, Sequence[str]] = None,
               cgrdir  : Union[None, str, Sequence[str]] = "cgr_dir",
               match   : str                             = None,
               allleaves = False,
               allaxes   = False,
               **kwargs):
        """
        Adds paths or tracks to the object as it would a normal directory.

        Using the specified keywords, it's also possible to scan for tracks.
        """
        if isinstance(tracks, dict):
            for i, j in tracks.items():
                self._set(i, j, allaxes)
            tracks = grs = cgrdir = match = None
        scan = {'cgrdir': cgrdir, 'allleaves': allleaves}
        for i in self._SCAN_OPTS:
            if i in kwargs:
                scan[i] = kwargs.pop(i)

        info = {} # type: ignore
        info.update(*args, **kwargs)
        for i, j in info.items():
            self._set(i, j, allaxes)

        if tracks is not None:
            assert sum(i is None for i in (tracks, grs)) in (0, 1, 2)
            self.scan(tracks, grs, match = match, allaxes = allaxes, **scan)
    if getattr(update, '__doc__', None):
        update.__doc__ += scan.__doc__[scan.__doc__.find('#')-5:] # pylint: disable=no-member

    def commonbeads(self, *keys) -> List[BEADKEY]:
        "returns the intersection of all beads in requested tracks (all by default)"
        if len(keys) == 0:
            keys = tuple(self.keys())

        fcn   = lambda key: set(cast(Track, self[key]).beadsonly.keys())
        beads = None # type: Optional[Set[BEADKEY]]
        with ThreadPoolExecutor(self._NTHREADS) as pool:
            for cur in pool.map(fcn, keys):
                beads = cur if beads is None else (cur & beads)

        return sorted(beads)

    def availablebeads(self, *keys):
        "returns available beads for provided oligos"
        if len(keys) == 0:
            keys = tuple(self.keys())

        fcn   = lambda key: set(cast(Track, self[key]).beadsonly.keys())
        beads = set() # type: Set[BEADKEY]
        with ThreadPoolExecutor(self._NTHREADS) as pool:
            for cur in pool.map(fcn, keys):
                beads.update(cur)
        return sorted(beads)

    def commonkeys(self, *abeads) -> List:
        "returns the intersection of all beads in requested tracks (all by default)"
        if len(abeads) == 0:
            return sorted(super().keys())

        beads = set(abeads)
        fcn   = lambda key: (key, len(beads - set(cast(Track, self[key]).beadsonly.keys())))
        keys  = [] # type: list
        with ThreadPoolExecutor(self._NTHREADS) as pool:
            for key, cur in pool.map(fcn, tuple(super().keys())):
                if cur == 0:
                    keys.append(key)

        return sorted(keys)

    def load(self, *args, **kwa) -> 'TracksDict':
        "Loads all the data. Args and kwargs are passed to a local patch mechanism."
        unloaded = [i for i in self.values() if not i.isloaded]
        def _run():
            with ThreadPoolExecutor(self._NTHREADS) as pool:
                for _ in pool.map(Track.load, unloaded):
                    pass

        if len(unloaded):
            if args or kwa:
                with LocalPatch(*args, **kwa):
                    _run()
            else:
                _run()
        return self
