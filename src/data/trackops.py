#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Operations on tracks
"""
from    copy        import copy as shallowcopy
from    typing      import Union, Tuple, List

import  numpy       as     np

from   .track       import Track
from   .views       import BEADKEY

def dropbeads(trk:Track, *beads:BEADKEY) -> Track:
    "returns a track without the given beads"
    trk.load()
    if len(beads) == 1 and isinstance(beads[0], (tuple, list, set, frozenset)):
        beads = tuple(beads[0])
    cpy           = shallowcopy(trk)
    good          = (frozenset(trk.data.keys()) - frozenset(beads)) | {'t', 'zmag'}
    cpy.data      = {i: trk.data[i] for i in good}

    cpy.fov       = shallowcopy(trk.fov)
    good          = good & frozenset(trk.fov.beads)
    cpy.fov.beads = {i: trk.fov.beads[i] for i in good}
    return cpy

def renamebeads(trk:Track, *beads:Tuple[BEADKEY, BEADKEY]) -> Track:
    "returns a track without the given beads"
    trk.load()
    cpy = shallowcopy(trk)
    rep = dict(beads)

    cpy.data      = {rep.get(i, i): j for i, j in trk.data.items()}
    cpy.fov       = shallowcopy(trk.fov)
    cpy.fov.beads = {rep.get(i, i): j for i, j in trk.fov.beads.items()}
    return cpy

def selectbeads(trk:Track, *beads:BEADKEY) -> Track:
    "returns a track without the given beads"
    if len(beads) == 1 and isinstance(beads[0], (tuple, list, set, frozenset)):
        beads = tuple(beads[0])
    return dropbeads(trk, *(set(trk.beadsonly.keys()) - set(beads)))

def selectcycles(trk:Track, indexes:Union[slice, range, List[int]])-> Track:
    """
    Returns a track with only a limited number of cycles
    """
    inds, phases = trk.phase.cut(indexes)
    track        = trk.__getstate__()
    track.update(data   = {i: j[inds] for i, j in trk.beads},
                 phases = phases,
                 path   = None)
    return  Track(**track)

def concatenatetracks(trk:Track, *tracks:Track)-> Track:
    """
    Concatenates two Tracks into a single one

    Data of beads are stacked. If the sets of beads are different, the missing
    data is set to np.NaN.

    This can be used to resume the recording an interrupted experiment
    """
    def _concatenate(trk1, trk2):
        shift  = trk1.data["t"][-1] - trk2.data["t"][0] +1
        phases = np.vstack([trk1.phases,trk2.phases+shift])
        time   = np.hstack([trk1.data["t"],trk2.data['t']+shift])
        beads  = set(trk1.data.keys()) | set(trk2.data.keys())

        values = np.zeros((len(beads),time.size))*np.nan

        for idx,val in enumerate(beads):
            if val in trk1.data.keys():
                values[idx,:trk1.data["t"].size]=trk1.data[val]
            if val in trk2.data.keys():
                values[idx,trk1.data["t"].size:]=trk2.data[val]

        data      = {j:values[i] for i,j in enumerate(beads)}
        data['t'] = time
        track     = trk1.__getstate__()
        track["data"]   = data
        track["phases"] = phases
        return  Track(**track)

    for other in tracks:
        trk = _concatenate(trk, other)
    return trk
