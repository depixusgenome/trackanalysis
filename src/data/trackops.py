#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Operations on tracks
"""
from    copy        import copy as shallowcopy, deepcopy
from    functools   import partial
from    typing      import Union, Tuple, List, TypeVar, Optional, cast
from    pathlib     import Path

import  numpy       as     np
import  pandas      as     pd

from   .track       import Track
from   .tracksdict  import TracksDict
from   .views       import BEADKEY, Beads

TRACKS = TypeVar('TRACKS', Track, TracksDict)

def _applytodict(fcn, trk, args, kwa) -> TracksDict:
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
                 phases = phases.astype('i4'))

    track['secondaries'] = secs = {i: trk.secondaries.data[i][inds] for i in ('t', 'zmag')}
    for i, j in trk.secondaries.data.items():
        if i not in secs:
            inds = np.clip(np.int32(j['index']-trk.phases[0,0]), 0, len(vals)-1)
            secs[i] = j[vals[inds]]

    start = None
    if trk.path:
        path  = Path(str(trk.path[0] if isinstance(trk.path, (list, tuple)) else trk.path))
        start = (
            indexes.stop  if getattr(indexes, 'stop',  None) is not None else
            indexes.start if getattr(indexes, 'start', None) else
            indexes[-1]   if hasattr(indexes, '__getitem__') else
            None
        )
    if start is not None:
        track['_modificationdate'] = (
            path.stat().st_ctime + trk.nframes/trk.framerate
            if start >= trk.phases.shape[0] else
            path.stat().st_ctime + trk.phases[start,0]/trk.framerate
        )

    trk = Track(**track)
    if start:
        setattr(trk, '_modificationdate', track['_modificationdate'])
    setattr(trk, '_lazydata_', False)

    return trk

def concatenatetracks(trk:TRACKS, *tracks:TRACKS)-> TRACKS:
    """
    Concatenates two Tracks into a single one

    Data of beads are stacked. If the sets of beads are different, the missing
    data is set to np.NaN.

    This can be used to resume the recording an interrupted experiment
    """
    def _concatenate(trk1, trk2):
        shift  = trk1.secondaries.frames[-1]-trk2.secondaries.frames[0]+1
        phases = np.vstack([trk1.phases,trk2.phases+shift])
        time   = np.hstack([trk1.secondaries.frames,trk2.secondaries.frames+shift])
        beads  = set(trk1.data.keys()) | set(trk2.data.keys())

        values = np.zeros((len(beads),time.size))*np.nan

        sz1    = trk1.secondaries.frames.size
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
    if path is None:
        return ""
    return Path(path[0] if isinstance(path, (list, tuple)) else path).stem

def _undersample_first(cnt, _, info):
    return (info[0], info[1][::cnt])

def _undersample_agg(fcn, cnt, _, info):
    arr = info[1]
    return (info[0], fcn(arr[:(len(arr)//cnt)*cnt].reshape((-1, cnt)), axis = 1))

def undersample(itm: Union[Track, Beads], cnt: int, agg: Optional[str] = None) -> Track:
    "undersample the track"
    track: Track = getattr(itm, 'track', itm)
    if cnt <= 1:
        return track

    track.load()
    # pylint: disable=protected-access
    cpy            = shallowcopy(track)
    cpy._phases    = np.copy(cpy.phases)//cnt
    if cpy.key is None:
        cpy.key   = str(track.path)
        cpy._path = None

    if agg in {None, 'none'}:
        fcn    = partial(_undersample_first, cnt)
    else:
        arrfcn = getattr(np, 'nan'+str(getattr(agg, '__name__', agg)).replace('nan', ''))
        # pylint: disable=not-callable
        fcn    = partial(_undersample_agg, arrfcn, cnt)

    def _temp(vals):
        vals            = np.copy(vals)
        vals['index'] //= cnt
        diff            = np.diff(vals['index']) > 0
        if np.any(diff):
            return np.concatenate([vals[:1], vals[1:][diff]])
        return vals

    cpy._data = (
        dict(fcn(None, i) for i in track._data.items())
        if isinstance(itm, Track) else
        itm.withaction(fcn)
    )

    cpy._secondaries    = dict(
        fcn(None, (i, j)) if i in ('t', 'zmag') else (i, _temp(j))
        for i, j in track._secondaries. items()
    )

    cpy.fov             = track.fov
    cpy.framerate       = track.framerate/cnt
    cpy._rawprecisions  = {}
    return cpy

def dataframe(track:Track) -> pd.DataFrame:
    "create a dataframe of the track"
    temps = 'tsink', 'tsample', 'tservo'
    def _temp(name):
        data = getattr(track.secondaries, name)
        arr  = np.full(track.nframes, np.NaN, dtype = 'f4')
        arr[data['index']-track.phases[0,0]] = data['value']
        return arr

    frame = pd.DataFrame(
        dict(
            **{f'b{i}': j for i, j in track.beads},
            **{i: getattr(track.secondaries, i) for i in ('zmag', 'phase', 'cid')},
            **{i: _temp(i) for i in temps}
        ),
        index = np.arange(track.nframes)+track.phases[0,0]
    )
    return frame
