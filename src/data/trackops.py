#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring,function-redefined,unused-argument
"""
Operations on tracks
"""
from    copy        import copy as shallowcopy, deepcopy
from    typing      import Union, Tuple, List, Optional, TypeVar, cast
from    pathlib     import Path

import  numpy       as     np

from   .track       import Track
from   .tracksdict  import TracksDict
from   .views       import BEADKEY

TRACKS = TypeVar('TRACKS', Track, TracksDict)

def _applytodict(fcn, trk, args, kwa) -> Optional[TracksDict]:
    cpy = shallowcopy(trk)
    for i, j in cpy.items():
        cpy[i] = fcn(j, *args, **kwa)
    return cpy

def dropbeads(trk:TRACKS, *beads:BEADKEY) -> TRACKS:
    "returns a track without the given beads"
    if isinstance(trk, TracksDict):
        return _applytodict(dropbeads, trk, beads, {})

    trk.load()
    if len(beads) == 1 and isinstance(beads[0], (tuple, list, set, frozenset)):
        beads = tuple(beads[0])
    cpy           = shallowcopy(trk)
    good          = frozenset(trk.data.keys()) - frozenset(beads)
    cpy.data      = {i: trk.data[i] for i in good}

    cpy.fov       = shallowcopy(trk.fov)
    good          = good & frozenset(trk.fov.beads)
    cpy.fov.beads = {i: trk.fov.beads[i] for i in good}
    setattr(cpy, '_secondaries', dict(getattr(trk, '_secondaries')))
    return cpy

def renamebeads(trk:TRACKS, *beads:Tuple[BEADKEY, BEADKEY]) -> TRACKS:
    "returns a track without the given beads"
    if isinstance(trk, TracksDict):
        return _applytodict(renamebeads, trk, beads, {})

    trk.load()
    cpy = shallowcopy(trk)
    rep = dict(beads)

    cpy.data      = {rep.get(i, i): j for i, j in trk.data.items()}
    cpy.fov       = shallowcopy(trk.fov)
    cpy.fov.beads = {rep.get(i, i): j for i, j in trk.fov.beads.items()}
    return cpy

def selectbeads(trk:TRACKS, *beads:BEADKEY) -> TRACKS:
    "returns a track without the given beads"
    if isinstance(trk, TracksDict):
        return _applytodict(selectbeads, trk, beads, {})

    if len(beads) == 1 and isinstance(beads[0], (tuple, list, set, frozenset)):
        beads = tuple(beads[0])
    return dropbeads(trk, *(set(trk.beads.keys()) - set(beads)))

def selectcycles(trk:TRACKS, indexes:Union[slice, range, List[int]])-> TRACKS:
    """
    Returns a track with only a limited number of cycles
    """
    if isinstance(trk, TracksDict):
        return _applytodict(selectcycles, trk, indexes, {})

    inds, phases = trk.phase.cut(indexes)
    vals         = np.zeros(trk.nframes, dtype = 'bool')
    vals[inds]   = True

    track        = trk.__getstate__()
    track.update(data   = {i: j[vals] for i, j in trk.beads},
                 phases = phases)

    track['secondaries'] = secs = {i: trk.secondaries.data[i][inds] for i in ('t', 'zmag')}
    for i, j in trk.secondaries.data.items():
        if i not in secs:
            inds = np.clip(np.int32(j['index']-trk.phases[0,0]), 0, len(vals)-1)
            secs[i] = j[vals[inds]]

    trk = Track(**track)
    trk._lazydata_ = False # type: ignore # pylint: disable=protected-access
    return trk

def concatenatetracks(trk:TRACKS, *tracks:TRACKS)-> TRACKS:
    """
    Concatenates two Tracks into a single one

    Data of beads are stacked. If the sets of beads are different, the missing
    data is set to np.NaN.

    This can be used to resume the recording an interrupted experiment
    """
    def _concatenate(trk1, trk2):
        shift  = trk1.secondaries.seconds[-1]-trk2.secondaries.seconds[0]+1
        phases = np.vstack([trk1.phases,trk2.phases+shift])
        time   = np.hstack([trk1.secondaries.seconds,trk2.secondaries.seconds+shift])
        beads  = set(trk1.data.keys()) | set(trk2.data.keys())

        values = np.zeros((len(beads),time.size))*np.nan

        sz1    = trk1.secondaries.seconds.size
        for idx,val in enumerate(beads):
            if val in trk1.data.keys():
                values[idx,:sz1]=trk1.data[val]
            if val in trk2.data.keys():
                values[idx, sz1:]=trk2.data[val]

        data      = {j:values[i] for i,j in enumerate(beads)}
        track     = trk1.__getstate__()
        track["data"]   = data
        track["phases"] = phases
        track["secondaries"] = {}

        for i, j in trk1.secondaries.data.items():
            if i == "t":
                track['secondaries']['t'] = time
            elif i == "zmag":
                track['secondaries']['zmag'] = np.hstack([j, trk2.secondaries.zmag])
            else:
                cpy                      = np.copy(trk2.secondaries.data[i])
                cpy['index']            += shift
                track["secondaries"][i]  = np.hstack([j, cpy])

        return  Track(**track)

    for other in tracks:
        trk = _concatenate(trk, other)
    return trk

def clone(trk:TRACKS)-> TRACKS:
    """
    Deeper shallow copy of the track.

    The track containers are copied but the numpy arrays are the same.
    """
    if isinstance(trk, Track):
        track = cast(Track, trk)
        state = track.__getstate__()
        state.pop('fov', None)
        state = deepcopy(state)
        for i in ('data', 'secondaries', 'fov'):
            state[i] = shallowcopy(getattr(track, f'_{i}'))
        return type(track)(**state)

    return type(trk)({i: clone(j) for i, j in cast(TracksDict, trk).items()})

def trackname(track:Track) -> str:
    "returns the track name"
    if track.key:
        return track.key

    path = track.path
    return Path(path if isinstance(path, (str, Path)) else path[0]).stem
