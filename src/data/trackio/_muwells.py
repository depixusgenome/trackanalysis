#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
from    typing                   import Tuple, Optional, cast
from    pathlib                  import Path
import  numpy                    as     np
from    numpy.lib.stride_tricks  import as_strided
import  pandas                   as     pd
from    legacy                   import readtrack # pylint: disable=no-name-in-module
from    ._base                   import TrackIO, PATHTYPE, PATHTYPES

class MuWellsFilesIO(TrackIO):
    "checks and opens legacy GR files"
    TRKEXT = '.trk'
    LIAEXT = '.txt'
    @classmethod
    def check(cls, path:PATHTYPES, **_) -> Optional[PATHTYPES]:
        "checks the existence of paths"
        if not isinstance(path, (list, tuple, set, frozenset)) or len(path) < 2:
            return None

        allpaths = tuple(Path(i) for i in cast(Tuple[PATHTYPE,...], path))
        if sum(1 for i in allpaths if i.suffix == cls.TRKEXT) != 1:
            return None

        if any(i.is_dir() for i in allpaths):
            raise IOError("µwell data file paths should not include directories")

        trk = next(i for i in allpaths if i.suffix == cls.TRKEXT)
        lia = tuple(i for i in allpaths if i.suffix  == cls.LIAEXT)
        if len(lia) == 0:
            return None

        return (trk,) + lia

    @staticmethod
    def instrumenttype(_) -> str:
        "return the instrument type"
        return "µwells"

    @classmethod
    def open(cls, paths:Tuple[PATHTYPE,PATHTYPE], **kwa) -> dict: # type: ignore
        "opens the directory"
        output = readtrack(str(paths[0]), clipcycles = False)
        if output is None:
            raise IOError(f"Could not open track '{paths[0]}'.\n"
                          "This could be because of a *root* mounted samba path")

        output              = {
            i: j
            for i, j in output.items()
            if not isinstance(i, int)
        }
        output['picofrate']  = output.pop("framerate", None)
        output['phases']     = output["phases"][kwa.get('clipcycles', 2):, :]
        output['instrument']["type"] = cls.instrumenttype(paths)
        output['instrument']["dimension"] = "V"
        for i, liapath in enumerate(paths[1:]):
            if Path(liapath).suffix == cls.LIAEXT:
                output.update(cls.__update(output, i, str(liapath), kwa))
        return output

    @classmethod
    def __update(cls, trk:dict, index, path:str, kwa:dict) -> dict:
        "verifies one gr"
        frames = pd.read_csv(
            path,
            sep    = kwa.get("sep", "[;,]"),
            header = kwa.get("header", 4),
            engine = kwa.get("engine", "python")
        )
        if not frames.shape[0]:
            return {}

        frate  = cls.__extractframerate(trk, frames, kwa)
        phases = cls.__extractphases(trk, frames, frate, kwa)
        last   = int(phases[-1,-1]+np.median(phases[1:,0]-phases[:-1,-1])+.5)
        phases = np.round(phases + .5).astype('i4')
        return {
            index:       frames[tuple(frames)[1]].values[phases[0,0]:last],
            'framerate': frate,
            'phases':    phases
        }

    @staticmethod
    def __extractframerate(trk, frames, kwa) -> float:
        cols      = tuple(frames)
        framerate = 1./frames[cols[0]].diff().median()
        if 'framerate' not in trk:
            return framerate

        delta = abs(framerate-trk['framerate'])
        if delta <= kwa.get('framerateapprox', 1e-1):
            return framerate

        msg = f"Framerate ({framerate}) differs from previous by {delta}"
        raise IOError(msg)

    @staticmethod
    def __extractdiffpeaks(trk, frames, kwa):
        phases = trk['phases']
        diff   = frames[tuple(frames)[1]].diff().values
        ncols  = phases.shape[0]
        cols   = diff[1:1+ncols*((len(diff)-1)//ncols)].reshape(ncols, -1)
        thr    = np.nanmedian(np.nanmax(cols, axis = 1))
        dist   = kwa.get("softthreshold", .1) * np.nanmedian(
            np.nanmax(cols, axis = 1) - np.nanmin(cols, axis = 1)
        )
        pks    = (diff[2:-1] > diff[1:-2]) & (diff[2:-1] > diff[3:])
        for i in range(5):
            inds    = 2+np.nonzero(pks & (diff[2:-1] > thr-dist*pow(.8, i)))[0]
            idiff   = np.diff(inds)
            meddist = int(np.median(idiff)*kwa.get('indexthreshold', .8))
            if not np.any(idiff < meddist):
                return inds
        raise IOError("Could not extract peak threshold")

    @staticmethod
    def __bestfit(left, right):
        assert len(right) < len(left)
        return np.argmax((
            (
                as_strided(
                    left,
                    strides = (left.strides[0],)*2,
                    shape   = (len(left) - len(right), len(right))
                )
                - right*np.nanmedian(left)/np.nanmedian(right)
            )**2
        ).sum(axis = 1))

    @classmethod
    def __extractphases(cls, trk, frames, framerate, kwa) -> np.ndarray:
        phases  = trk['phases']
        indamp  =  cls.__extractdiffpeaks(trk, frames, kwa)
        delttrk = phases[1:,2]-phases[:-1,2]
        deltamp = np.diff(indamp)
        good    = (
            0                                if len(deltamp) == len(delttrk) else
            -cls.__bestfit(deltamp, delttrk) if len(deltamp) > len(delttrk)  else
            cls.__bestfit(delttrk, deltamp)
        )

        delttrk = np.append(delttrk, np.nanmedian(delttrk))
        deltamp = np.append(deltamp, np.nanmedian(deltamp))
        bias    = kwa.get("indexbias", -7)*framerate/trk['picofrate']
        return bias + np.vstack([
            np.round((phases[i,:]-phases[i,2])* (k/j)+.5).astype('i4') + l
            for i, j, k, l in zip(
                range(max(0, good), phases.shape[0]),
                delttrk[max(0, good):],
                deltamp[max(0, -good):],
                indamp[max(0, -good):]
            )
        ])
