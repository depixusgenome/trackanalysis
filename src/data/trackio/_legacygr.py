#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
from    typing             import Sequence, Union, Tuple, Optional, Iterator, Dict, cast
from    itertools          import chain
from    functools          import partial
from    pathlib            import Path
import  re
import  numpy              as     np

# pylint: disable=import-error,no-name-in-module
from    legacy             import readgr, instrumenttype  as _legacyinstrumenttype
from    ._base             import TrackIO, PATHTYPE, PATHTYPES, globfiles
from    ._legacy           import LegacyTrackIO

class LegacyGRFilesIO(TrackIO):
    "checks and opens legacy GR files"
    TRKEXT    = '.trk'
    GREXT     = '.gr'
    CGREXT    = '.cgr'
    __GRDIR   = 'cgr_project'
    __TITLE   = re.compile(r"\\stack{{Bead (?P<id>\d+) Z.*?phase\(s\)"
                           r"(?:[^\d]|\d(?!,))*(?P<phases>[\d, ]*?)\].*?}}")
    __GRTITLE = re.compile(r"Bead Cycle (?P<id>\d+) p.*")
    @classmethod
    def check(cls, path:PATHTYPES, **kwa) -> Optional[PATHTYPES]:
        "checks the existence of paths"
        if not isinstance(path, (list, tuple, set, frozenset)) or len(path) < 2:
            return None

        allpaths = tuple(Path(i) for i in cast(Tuple[PATHTYPE,...], path))
        if sum(1 for i in allpaths if i.suffix == cls.TRKEXT) != 1:
            return None

        if any(i.suffix == cls.CGREXT for i in allpaths):
            if len(allpaths) == 2:
                allpaths = tuple(i if i.suffix == cls.TRKEXT else i.parent for i in allpaths)
            else:
                allpaths = tuple(i for i in allpaths if i.suffix != cls.CGREXT)

        if len(allpaths) == 2 and any(i.is_dir() for i in allpaths):
            allpaths = cls.__findgrs(allpaths, kwa)
            fname    = str(allpaths[0])
            if '*' in fname:
                return cls.__findtrk(fname, allpaths[1])

            if not allpaths[0].exists():
                raise IOError("Could not find path: " + str(allpaths[0]), "warning")

            return allpaths

        trk = next(i for i in allpaths if i.suffix == cls.TRKEXT)
        grs = tuple(i for i in allpaths if i.suffix  == cls.GREXT)
        if len(grs) == 0:
            return None

        return (trk,) + grs

    @staticmethod
    def instrumenttype(path: str) -> str:
        "return the instrument type"
        return _legacyinstrumenttype(path)

    @classmethod
    def open(cls, paths:Tuple[PATHTYPE,PATHTYPE], **kwa) -> dict: # type: ignore
        "opens the directory"
        output = LegacyTrackIO.open(paths[0], **kwa)
        if output is None:
            raise IOError(f"Could not open track '{paths[0]}'.\n"
                          "This could be because of a *root* mounted samba path")
        remove = set(i for i in output if isinstance(i, int))

        if len(paths) == 2 and Path(paths[1]).is_dir():
            itr : Iterator[Path] = iter(i for i in Path(paths[1]).iterdir()
                                        if 'z(t)bd' in i.stem.lower())
        else:
            itr = (Path(i) for i in paths[1:])

        # in case of axis != 'Z: we keep a backup,
        # find which beads are valid and recover only these
        axis   = kwa.pop('axis', 'Z')
        axis   = getattr(axis, 'value', axis)[0]
        backup = dict(output) if axis != 'Z' else output

        for grpath in itr:
            if grpath.suffix == cls.GREXT:
                remove.discard(cls.__update(str(grpath), output))

        output = backup # this only affects axis != 'Z'
        for key in remove:
            output.pop(key)
        return output

    @classmethod
    def __findgrs(cls, paths, opts):
        grdir  = opts.get('cgrdir', cls.__GRDIR)
        ext    = (cls.GREXT,)
        err    = lambda j: IOError(j+'\n -'+ '\n -'.join(str(i) for i in paths), 'warning')
        hasgr  = lambda i: (i.is_dir()
                            and (i.name == grdir
                                 or any(j.suffix in ext for j in i.iterdir())))

        grs    = [hasgr(i) for i in paths]
        direct = sum(i for i in grs)

        if direct == 0:
            grs    = [hasgr(i/grdir) for i in paths]
            direct = sum(i for i in grs)

            if direct == 0:
                raise err("No .gr files in directory:")

            if direct > 1:
                raise err("All sub-directories have .gr files:")

            return paths[1 if grs[0] else 0], paths[0 if grs[0] else 1]/grdir

        if direct > 1:
            raise err("All directories have .gr files:")

        return paths[1 if grs[0] else 0], paths[0 if grs[0] else 1]

    @classmethod
    def __findtrk(cls, fname:str, grs:PATHTYPE) -> Tuple[PATHTYPE,PATHTYPE]:
        cgr  = next((i for i in Path(grs).iterdir() if i.suffix == cls.CGREXT),
                    None)
        if cgr is None:
            raise IOError(f"No {cls.CGREXT} files in directory\n- {grs}", "warning")

        pot = cgr.with_suffix(cls.TRKEXT).name
        trk = next((i for i in globfiles(fname) if i.name == pot), None)
        if trk is None:
            raise IOError(f"Could not find {pot} in {fname}", "warning")
        return trk, grs

    @classmethod
    def __update(cls, path:str, output:dict) -> int:
        "verifies one gr"
        grdict = readgr(path)
        tit    = cls.__TITLE.match(grdict['title'].decode("utf8", "replace"))

        if tit is None:
            raise IOError("Could not match title in " + path, "warning")

        beadid = int(tit.group("id"))
        if beadid not in output:
            raise IOError("Could not find bead "+str(beadid)+" in " + path, "warning")

        phases = [int(i) for i in tit.group("phases").split(',') if len(i.strip())]
        if set(np.diff(phases)) != {1}:
            raise IOError("Phases must be sequencial in "+ path, "warning")

        starts  = output['phases'][:, phases[0]] - output['phases'][0,0]
        bead    = output[beadid]
        bead[:] = np.NaN
        for title, vals in grdict.items():
            if not isinstance(title, bytes):
                continue
            tit = cls.__GRTITLE.match(title.decode("utf8", "replace"))
            if tit is None:
                continue

            cyc  = int(tit.group("id")) - output['cyclemin']
            if cyc >= len(starts):
                continue

            inds = np.int32(vals[0]+.1+starts[cyc]) # type: ignore
            try:
                bead[inds] = vals[1]
            except IndexError as err:
                raise IOError(f"updating {path} raised {err.__str__}")
        return beadid

    @classmethod
    def __scan(cls, lst, fcn) -> Dict[str, Path]:
        return {i.stem: i for i in chain.from_iterable(globfiles(fcn(str(k))) for k in lst)}

    @classmethod
    def scantrk(cls, trkdirs) -> Dict[str, Path]:
        "scan for track files"
        if not isinstance(trkdirs, (tuple, list, set, frozenset)):
            trkdirs = (trkdirs,)
        return {i.stem: i for i in LegacyTrackIO.scan(trkdirs)}

    @classmethod
    def scangrs(cls, grdirs, cgrdir = None, allleaves = False, **_) -> Dict[str, Path]:
        "scan for gr files"
        if not isinstance(grdirs, (tuple, list, set, frozenset)):
            grdirs = (grdirs,)

        grdirs   = tuple(str(i) for i in grdirs)
        projects = ((None,)         if allleaves                else
                    (cgrdir,)       if isinstance(cgrdir, str)  else
                    (cls.__GRDIR,)  if cgrdir is None           else
                    cgrdir)

        res = {}
        fcn = lambda match, grdir, i: (i if match(i) or cls.CGREXT in i else i + grdir)
        for proj in projects:
            if proj:
                grdir = f'/**/{proj}/*{cls.CGREXT}'
                part  = partial(fcn, re.compile(rf'\b{proj}\b').search, grdir)
            elif not allleaves:
                part  = partial(fcn, lambda _: False, '')
            else:
                grdir = f'/**/*{cls.GREXT}'
                part  = partial(fcn, lambda _: '*' in _, grdir)

            update = cls.__scan(grdirs, part)
            if allleaves:
                # add check on gr-files
                res.update({Path(_).parent.stem: Path(_).parent
                            for _ in update.values()
                            if cls.GREXT in _.suffixes})
            else:
                res.update(update)
        return res

    @classmethod
    def scan(cls,
             trkdirs: Union[str, Sequence[str]],
             grdirs:  Union[str, Sequence[str]],
             **opts
            ) -> Tuple[Tuple[PATHTYPES,...], Tuple[PATHTYPES,...], Tuple[PATHTYPES,...]]:
        """
        Scans for pairs

        Returns:

            * pairs of (trk file, gr directory)
            * gr directories with missing trk files
            * trk files with missing gr directories
        """
        trks     = cls.scantrk(trkdirs)
        cgrs     = cls.scangrs(grdirs, **opts)
        rep      = lambda i: i.parent if i.is_file() else i
        pairs    = frozenset(trks) & frozenset(cgrs)
        good     = tuple((trks[i], rep(cgrs[i])) for i in pairs)
        lonegrs  = tuple(rep(cgrs[i])            for i in frozenset(cgrs) - pairs)
        lonetrks = tuple(trks[i]                 for i in frozenset(trks) - pairs)
        return good, lonegrs, lonetrks
