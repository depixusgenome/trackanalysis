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
from    legacy                   import readtrack  # pylint: disable=no-name-in-module
from    utils                    import initdefaults
from    ._base                   import TrackIO, PATHTYPE, PATHTYPES, TrackIOError

class LIAFilesIOConfiguration:
    "model for opening LIA files"
    name:            str       = "track.open.liafile"
    clipcycles:      int       = 2
    sep:             str       = "[;,]"
    header:          int       = 4
    engine:          str       = "python"
    indexbias:       int       = -7
    colnames:        str       = '% Time (s), Amplitude (V)'
    maxcycles:       float     = 1.3
    indexpower:      float     = .8
    indexthreshold:  float     = .8
    maxdistanceratio:float     = .025
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
    LEGACY  = -500
    DEFAULT = LIAFilesIOConfiguration()
    TRKEXT  = '.trk'
    LIAEXT  = '.txt'
    @classmethod
    def check(cls, path:PATHTYPES, **kwa) -> Optional[PATHTYPES]:
        "checks the existence of paths"
        if not isinstance(path, (list, tuple, set, frozenset)):
            path = (path,)

        allpaths = tuple(Path(i) for i in cast(Tuple[PATHTYPE,...], path))
        if sum(1 for i in allpaths if i.suffix == cls.TRKEXT) != 1:
            return None

        if any(i.is_dir() for i in allpaths):
            return None

        if len(allpaths) == 1:
            text = allpaths[0].with_suffix(cls.LIAEXT)
            if not text.exists():
                text = Path(*(
                    cls.LIAEXT[1:] if i == cls.TRKEXT[1:] else i for i in text.parts
                ))
                if not text.exists():
                    return None
            allpaths += (text,)

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
    def instrumentinfo(_) -> Dict[str, Any]:
        "return the instrument type"
        return {'type': "muwells", "dimension": "µV", 'name': None}

    @classmethod
    def open(cls, paths:Tuple[PATHTYPE,PATHTYPE], **kwa) -> dict:  # type: ignore
        "opens the directory"
        cnf    = LIAFilesIOConfiguration(**dict(cls.DEFAULT.config(), **kwa))

        output = readtrack(str(paths[0]), clipcycles = False)
        if output is None:
            raise TrackIOError(
                f"Could not open track '{paths[0]}'.\n"
                "This could be because of a *root* mounted samba path"
            )

        output              = {
            i: j
            for i, j in output.items()
            if not isinstance(i, int)
        }
        output['picofrate']  = output.pop("framerate", None)
        output['phases']     = output["phases"][cnf.clipcycles:, :]
        output['instrument'] = cls.instrumentinfo(paths)
        output['sequencelength']     = {}
        output['experimentallength'] = {}
        for i, liapath in enumerate(paths[1:]):
            if Path(liapath).suffix == cls.LIAEXT:
                cls.__update(output, i, str(liapath), cnf)

        if not any(isinstance(i, int) for i in output):
            raise TrackIOError("Could not add µwells data to the current track")

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
        if np.any(np.diff(phases.ravel()) <= 0):
            raise TrackIOError("Could not synchronize the files: incorrect phases", "warning")

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
        raise TrackIOError(msg)

    @classmethod
    def __extractdiffpeaks(cls, trk, frames, cnf):
        def _extract():
            diff   = frames[tuple(frames)[1]].diff().values
            ncols  = trk['phases'].shape[0]
            cols   = diff[1:1+ncols*((len(diff)-1)//ncols)].reshape(ncols, -1)
            thr    = np.nanmedian(np.nanmax(cols, axis = 1))
            dist   = cnf.softthreshold * np.nanmedian(
                np.nanmax(cols, axis = 1) - np.nanmin(cols, axis = 1)
            )
            pks    = (diff[2:-1] > diff[1:-2]) & (diff[2:-1] > diff[3:])
            for i in range(5):
                inds    = 2+np.nonzero(
                    pks
                    & (diff[2:-1] > thr-dist*pow(cnf.indexpower, i))
                )[0]
                idiff   = np.diff(inds)
                meddist = np.median(idiff)
                good    = np.ones(len(inds), dtype = 'bool')
                for j in np.nonzero(idiff < meddist*cnf.indexthreshold)[0]:
                    delta  = (inds-inds[j])/meddist
                    delta -= np.round(delta)
                    if np.abs(np.mean(delta)) > cnf.maxdistanceratio:
                        good[j] = False

                    delta  = (inds-inds[j+1])/meddist
                    delta -= np.round(delta)
                    if np.abs(np.mean(delta)) > cnf.maxdistanceratio:
                        good[j+1] = False

                inds = inds[good]
                if len(inds) < 2:
                    continue
                meddist = int(np.median(np.diff(inds)))
                out = np.concatenate(
                    [
                        list(range(inds[i],inds[i+1]-meddist//2, meddist))
                        for i in range(len(inds)-1)
                    ]
                    +[inds[-1:]]
                )
                if len(out) < cnf.maxcycles*trk['phases'].shape[0]:
                    return out
            return None

        inds1        = _extract()
        name         = tuple(frames)[1]
        frames[name] = -frames[name]
        inds2        = _extract()
        if inds2 is None and inds1 is None:
            raise TrackIOError("Could not extract peak threshold")
        if inds2 is not None and (inds1 is None or len(inds1) < len(inds2)):
            return inds2
        frames[name] = -frames[name]
        return inds1

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
        indamp  = cls.__extractdiffpeaks(trk, frames, cnf)
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
        phases  = bias + np.vstack([
            np.round((phases[i,:]-phases[i,2]) * (k/j)+.5).astype('i4') + l
            for i, j, k, l in zip(
                range(max(0, good), phases.shape[0]),
                delttrk[max(0, good):],
                deltamp[max(0, -good):],
                indamp[max(0, -good):]
            )
        ])

        for ind in range(phases.shape[0]):
            if phases[ind, 0] >= 0:
                return phases[ind:,]
        return phases[:0,:]
