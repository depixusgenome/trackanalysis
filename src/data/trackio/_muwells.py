#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
from    typing                   import Tuple, Optional, Dict, Any, List, cast
from    pathlib                  import Path
import  numpy                    as     np
from    numpy.lib.stride_tricks  import as_strided
from    scipy.interpolate        import interp1d
import  pandas                   as     pd
from    legacy                   import readtrack # pylint: disable=no-name-in-module
from    utils                    import initdefaults
from    ._base                   import TrackIO, PATHTYPE, PATHTYPES

class LIAFilesIOConfiguration:
    "model for opening LIA files"
    name:            str = "track.open.liafile"
    clipcycles:      int = 2
    sep:             str = "[;,]"
    header:          int = 4
    engine:          str ="python"
    indexbias:       int = -7
    colnames:        str = '% Time (s), Amplitude (V)'
    indexthreshold:  float     = .8
    softthreshold:   float     = .1
    framerateapprox: float     = .1
    phases:          List[int] = [1, 4]
    population:      List[int] = [1, 99]

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def config(self) -> Dict[str, Any]:
        "return the dictionnary"
        return dict(self.__dict__)

    def open(self, paths: PATHTYPES):
        "open a track file"
        lst = MuWellsFilesIO.check(paths)
        if not lst:
            return None

        return MuWellsFilesIO.open(lst, **self.config())

class MuWellsFilesIO(TrackIO):
    "checks and opens legacy GR files"
    DEFAULT = LIAFilesIOConfiguration()
    TRKEXT  = '.trk'
    LIAEXT  = '.txt'
    @classmethod
    def check(cls, path:PATHTYPES, **kwa) -> Optional[PATHTYPES]:
        "checks the existence of paths"
        if not isinstance(path, (list, tuple, set, frozenset)) or len(path) < 2:
            return None

        allpaths = tuple(Path(i) for i in cast(Tuple[PATHTYPE,...], path))
        if sum(1 for i in allpaths if i.suffix == cls.TRKEXT) != 1:
            return None

        if any(i.is_dir() for i in allpaths):
            raise IOError("µwell data file paths should not include directories")

        cnf = LIAFilesIOConfiguration(**dict(cls.DEFAULT.config(), **kwa))
        trk = next(i for i in allpaths if i.suffix == cls.TRKEXT)
        lia: Tuple[Path, ...] = ()
        for itm in (i for i in allpaths if i.suffix  == cls.LIAEXT):
            with open(itm, "r", encoding = "utf-8") as stream:
                lines = [line.strip() for __, line in zip(range(cnf.header+2), stream)]
                if not (
                        len(lines) != cnf.header+2
                        or any(line[0] != '%' for line in lines[:-1])
                        or lines[-1][0] == '%'
                        or cnf.colnames not in lines
                ):
                    lia += (itm,)

        if len(lia) == 0:
            return None

        return (trk,) + lia

    @staticmethod
    def instrumenttype(_) -> str:
        "return the instrument type"
        return "muwells"

    @classmethod
    def open(cls, paths:Tuple[PATHTYPE,PATHTYPE], **kwa) -> dict: # type: ignore
        "opens the directory"
        cnf    = LIAFilesIOConfiguration(**dict(cls.DEFAULT.config(), **kwa))

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
        output['phases']     = output["phases"][cnf.clipcycles:, :]
        output['instrument']["type"] = cls.instrumenttype(paths)
        output['instrument']["dimension"] = "µV"
        output['sequencelength']     = {}
        output['experimentallength'] = {}
        for i, liapath in enumerate(paths[1:]):
            if Path(liapath).suffix == cls.LIAEXT:
                cls.__update(output, i, str(liapath), cnf)

        if not any(isinstance(i, int) for i in output):
            raise IOError("Could not add µwells data to the current track")

        cls.__correctsecondaries(output)
        return output

    @staticmethod
    def __correctsecondaries(output: dict):
        if output['picofrate'] == output['framerate']:
            return

        ratio   = output['framerate']/output['picofrate']
        nframes = next(len(j) for i, j in output.items() if isinstance(i, int))
        for key in output:
            if not isinstance(key, str):
                continue

            if key.startswith("T") or key == 'vcap':
                output[key] = (
                    np.round(output[key][0]*ratio).astype('i4'),
                    *output[key][1:]
                )

            elif key == 'zmag':
                output[key] = interp1d(
                    np.arange(len(output[key]))*ratio,
                    output[key],
                    assume_sorted = True,
                    fill_value    = np.NaN,
                    bounds_error  = False
                )(np.arange(nframes))

    @staticmethod
    def __seqlen(path):
        with open(path) as stream:
            for line in stream:
                if line[0] != '%':
                    break
                if 'sequence:' in line:
                    return int(line[line.rfind(':')+1:].strip())
        return None

    @staticmethod
    def __explen(phases, arr, cnf:LIAFilesIOConfiguration):
        pha    = cnf.phases
        perc   = cnf.population
        return np.median([
            np.diff(np.nanpercentile(arr[phases[i][pha[0]]:phases[i][pha[1]]], perc))[0]
            for i in range(phases.shape[0])
        ])

    @classmethod
    def __update(cls, trk:dict, index, path:str, cnf:LIAFilesIOConfiguration):
        "verifies one gr"
        frames = pd.read_csv(
            path,
            sep    = cnf.sep,
            header = cnf.header,
            engine = cnf.engine
        )
        if not frames.shape[0]:
            return

        frate  = cls.__extractframerate(trk, frames, cnf)
        phases = cls.__extractphases(trk, frames, frate, cnf)
        last   = int(phases[-1,-1]+np.median(phases[1:,0]-phases[:-1,-1])+.5)
        phases = np.round(phases + .5).astype('i4')
        arr    = frames[tuple(frames)[1]].values.astype('f4')
        if '(V)' in frames.columns[1]:
            arr *= 1e6
        else:
            raise NotImplementedError(f"Tension should be in (V) : {frames.columns[1]}")

        trk.update({
            index:                arr[phases[0,0]:last],
            'framerate':          frate,
            'phases':             phases,
        })
        trk['sequencelength'][index]     = cls.__seqlen(path)
        trk['experimentallength'][index] = cls.__explen(phases, arr, cnf)

    @staticmethod
    def __extractframerate(trk, frames, cnf) -> float:
        cols      = tuple(frames)
        framerate = 1./frames[cols[0]].diff().median()
        if 'framerate' not in trk:
            return framerate

        delta = abs(framerate-trk['framerate'])
        if delta <= cnf.framerateapprox:
            return framerate

        msg = f"Framerate ({framerate}) differs from previous by {delta}"
        raise IOError(msg)

    @staticmethod
    def __extractdiffpeaks(trk, frames, cnf):
        phases = trk['phases']
        diff   = frames[tuple(frames)[1]].diff().values
        ncols  = phases.shape[0]
        cols   = diff[1:1+ncols*((len(diff)-1)//ncols)].reshape(ncols, -1)
        thr    = np.nanmedian(np.nanmax(cols, axis = 1))
        dist   = cnf.softthreshold * np.nanmedian(
            np.nanmax(cols, axis = 1) - np.nanmin(cols, axis = 1)
        )
        pks    = (diff[2:-1] > diff[1:-2]) & (diff[2:-1] > diff[3:])
        for i in range(5):
            inds    = 2+np.nonzero(pks & (diff[2:-1] > thr-dist*pow(.8, i)))[0]
            idiff   = np.diff(inds)
            meddist = int(np.median(idiff)*cnf.indexthreshold)
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
    def __extractphases(cls, trk, frames, framerate, cnf) -> np.ndarray:
        phases  = trk['phases']
        indamp  =  cls.__extractdiffpeaks(trk, frames, cnf)
        delttrk = phases[1:,2]-phases[:-1,2]
        deltamp = np.diff(indamp)
        good    = (
            0                                if len(deltamp) == len(delttrk) else
            -cls.__bestfit(deltamp, delttrk) if len(deltamp) > len(delttrk)  else
            cls.__bestfit(delttrk, deltamp)
        )

        delttrk = np.append(delttrk, np.nanmedian(delttrk))
        deltamp = np.append(deltamp, np.nanmedian(deltamp))
        bias    = cnf.indexbias*framerate/trk['picofrate']
        return bias + np.vstack([
            np.round((phases[i,:]-phases[i,2])* (k/j)+.5).astype('i4') + l
            for i, j, k, l in zip(
                range(max(0, good), phases.shape[0]),
                delttrk[max(0, good):],
                deltamp[max(0, -good):],
                indamp[max(0, -good):]
            )
        ])
