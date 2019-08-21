#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Operations on tracks
"""
from    copy        import copy as shallowcopy, deepcopy
from    functools   import partial
from    typing      import Union, Tuple, List, TypeVar, Any, Dict, Optional, cast
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

def selectcycles(trk:Union[TRACKS, Beads], indexes:Union[slice, range, List[int]])-> TRACKS:
    """
    Returns a copy of a Track or TracksDict instance with only a limited number
    of its cycles.

    Parameters
    ----------
    trk:
        the Beads, Track or TracksDict instance to clip
    indexes:
        the cycles to select

    Returns
    -------
    Either a Track or a TracksDict instance, depending on whether one or the
    other was used as the first argument.
    """
    if isinstance(trk, TracksDict):
        return _applytodict(selectcycles, trk, indexes, {})

    root: Track  = trk if isinstance(trk, Track) else trk.track
    if isinstance(indexes, (range, slice)):
        # if no changes required: send back the track unchanged
        rng: range = cast(range, indexes)
        if (
                not rng.start
                and rng.stop and rng.stop >= root.ncycles
                and rng.step == 1
        ):
            return trk
    root.load()

    inds, phases = root.phase.cut(indexes)
    vals         = np.zeros(root.nframes, dtype = 'bool')
    vals[inds]   = True

    track: Dict[str, Any] = root.__getstate__()
    track.update(
        phases = phases.astype('i4'),
        data   = (
            trk.withaction(lambda _, info: (info[0], info[1][vals]))
            if isinstance(trk, Beads) else
            {i: j[vals] for i, j in root.beads}
        )
    )

    track['secondaries'] = secs = {i: root.secondaries.data[i][inds] for i in ('t', 'zmag')}
    for i, j in root.secondaries.data.items():
        if i not in secs:
            inds = np.clip(np.int32(j['index']-root.phases[0,0]), 0, len(vals)-1)
            secs[i] = j[vals[inds]]

    start: Optional[int] = None
    if root.path:
        path  = Path(str(root.path[0] if isinstance(root.path, (list, tuple)) else root.path))
        start = (
            cast(slice, indexes).stop    if getattr(indexes, 'stop',  None) is not None else
            cast(slice, indexes).start   if getattr(indexes, 'start', None) else
            cast(List[int], indexes)[-1] if hasattr(indexes, '__getitem__') else
            None
        )
    if start is not None:
        track['_modificationdate'] = (
            path.stat().st_ctime + root.nframes/root.framerate
            if start >= root.phases.shape[0] else
            path.stat().st_ctime + root.phases[start,0]/root.framerate
        )

    out: Track = Track(**track)
    if start:
        setattr(out, '_modificationdate', track['_modificationdate'])
    setattr(out, '_lazydata_', False)

    return out

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

def undersample(
        itm:    Union[Track, Beads],
        cnt:    int,
        agg:    Optional[str]   = None,
        cycles: Optional[range] = None
) -> Track:
    """
    Returns a copy of a Track or TracksDict instance with only a fraction of
    the number of frames. Each new frame is a measure on `cnt` frames, the
    latter being defined by `agg`.

    It's also possible to reduce the number of cycles using `cycles`

    Parameters
    ----------
    itm:
        The Track or Beads instance to clip
    cnt:
        The fraction of frames to keep
    agg:
        The name of the function to use for reducing each consecutive `cnt` frames.
    cycles:
        If not `None`, the cycles to keep, see `selectcycles`
    """
    if cycles is not None:
        root: Track = selectcycles(itm, cycles)
        if cnt <= 1:
            return getattr(root, 'track', root)
    elif cnt <= 1:
        return getattr(itm, 'track', itm)
    else:
        root = itm if isinstance(itm, Track) else itm.track

    # already loaded in selectcycles
    root.load()

    track: Dict[str, Any] = root.__getstate__()
    track['_lazydata_']   = False
    track['phases']       = np.copy(track['phases'])//cnt
    if track.get('key', None) is None:
        track['key']  = root.path
        track['path'] = None

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

    track['data'] = (
        itm.withaction(fcn)                    if isinstance(itm, Beads) else
        getattr(root, '_data').withaction(fcn) if isinstance(getattr(root, '_data'), Beads) else
        dict(fcn(None, i) for i in getattr(root, "_data").items())
    )

    track['secondaries'] = dict(
        fcn(None, (i, j)) if i in ('t', 'zmag') else (i, _temp(j))
        for i, j in getattr(root, '_secondaries'). items()
    )

    track['fov']            = root.fov
    track['framerate']      = root.framerate/cnt

    out = Track(**track)
    if '_modificationdate' in track:
        setattr(out, '_modificationdate', track['_modificationdate'])
    setattr(out, '_rawprecisions',  {})
    setattr(out, '_lazydata_',      False)
    return out

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
