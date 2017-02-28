#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Loading and save tracks"
from    typing      import Sequence, Any, Union
from    inspect     import signature
import  pickle
import  re
from    functools   import wraps
from    pathlib     import Path
import  numpy       as     np

from    legacy      import readtrack, readgr # pylint: disable=import-error,no-name-in-module

PATHTYPE = Union[str, Path]
class _NotMine(Exception):
    pass

def _fromdict(fcn):
    sig = signature(fcn)
    tpe = next(iter(sig.parameters.values())).annotation
    if tpe is sig.empty:
        tpe = Any
    else:
        tpe = getattr(tpe, '__union_params__', tpe)

    @wraps(fcn)
    def _wrapper(track):
        if isinstance(track.path, tpe):
            kwargs = fcn(track.path)
        else:
            raise _NotMine()

        if kwargs is None:
            track.data = dict()
        else:
            for name in {'phases', 'framerate'} & set(kwargs):
                setattr(track, name, kwargs.pop(name))

            track.data = dict(ite for ite in kwargs.items()
                              if isinstance(ite[1], np.ndarray))
    return _wrapper

@_fromdict
def _open_pickle(path:PATHTYPE):
    if Path(path).suffix == ".pk":
        with open(str(path), 'rb') as stream:
            return pickle.load(stream)
    else:
        raise _NotMine()

@_fromdict
def _open_legacytracks(path:PATHTYPE):
    if Path(path).suffix == ".trk":
        return readtrack(str(path))
    else:
        raise _NotMine()

class _GRDirectory:
    TITLE   = re.compile(r"\\stack{{Bead (?P<id>\d+) Z.*?phase\(s\)"
                         +r" \[(?P<phases>.*?)\]}}")
    GRTITLE = re.compile(r"Bead Cycle (?P<id>\d+) p.*")
    def __init__(self, paths):
        self.paths  = paths

    def open(self):
        u"opens the directory"
        output = readtrack(str(self.paths[0]))
        remove = set(i for i in output if isinstance(i, int))

        for grpath in Path(self.paths[1]).iterdir():
            if grpath.suffix != ".gr":
                continue

            remove.discard(self.update(str(grpath), output))

        for key in remove:
            output.pop(key)
        return output

    def update(self, path:str, output:dict) -> int:
        u"verifies one gr"
        grdict = readgr(path)
        tit    = self.TITLE.match(grdict['title'])

        if tit is None:
            raise IOError("Could not match title in " + path)

        beadid = int(tit.group("id"))
        if beadid not in output:
            raise IOError("Could not find bead "+str(beadid)+" in " + path)

        phases = [int(i) for i in tit.group("phases").split(',')]
        if set(np.diff(phases)) != {1}:
            raise IOError("Phases must be sequencial in "+ path)

        starts  = output['phases'][:, phases[0]] - output['phases'][0,phases[0]]
        bead    = output[beadid]
        bead[:] = np.NaN
        for title, vals in grdict.items():
            tit = self.GRTITLE.match(title)
            if tit is None:
                continue

            cyc  = int(tit.group("id")) - output['cyclemin']
            inds = np.int32(vals[0]+.1+starts[cyc]) # type: ignore
            bead[inds] = vals[1]
        return beadid

@_fromdict
def _open_legacygrdirectory(paths:Sequence[PATHTYPE]):
    if Path(paths[1]).suffix == ".trk":
        paths = paths[1], paths[0]

    if Path(paths[0]).suffix != ".trk":
        raise _NotMine()

    path = Path(paths[1])
    if not path.is_dir() or not any(i.suffix == '.gr' for i in path.iterdir()):
        raise _NotMine()

    return _GRDirectory(paths).open()

_CALLERS = tuple(fcn for name, fcn in locals().items() if name.startswith('_open_'))

def opentrack(track, beadsonly = False):
    u"Opens a track depending on its extension"
    paths = getattr(track, 'path', track)
    if isinstance(paths, (str, Path)):
        paths = str(paths),
    else:
        paths = tuple(str(i) for i in paths)

    for path in paths:
        if not Path(path).exists():
            raise IOError("Could not find path: " + str(path))

    if isinstance(track, (str, Path, tuple, list)):
        from .track import Track
        track = Track(path = paths[0] if len(paths) == 1 else paths)

    for caller in _CALLERS:
        try:
            caller(track)
        except _NotMine:
            continue
        break
    else:
        raise IOError("Unknown file format in: " + str(paths))

    if beadsonly:
        for key in {i for i in track.data if not track.isbeadname(i)}:
            track.data.pop(key) # pylint: disable=no-member
    return track
