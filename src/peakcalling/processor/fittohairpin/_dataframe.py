#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing                      import (
    Dict, Sequence, List, Tuple, Optional, Callable, Pattern, ClassVar, cast
)

import numpy                       as     np
import pandas                      as     pd

from   peakfinding.processor           import PeakStatusComputer
from   peakfinding.processor.dataframe import PeaksDataFrameFactory
from   sequences                       import peaks as _peaks
from   taskcontrol.processor.dataframe import DataFrameFactory, DataFrameTask
from   ...tohairpin                    import HairpinFitter
from   ._model                         import FitBead, FitToHairpinTask
from   ._dict                          import FitToHairpinDict


@DataFrameFactory.adddoc
class FitsDataFrameFactory(DataFrameFactory[FitToHairpinDict]):
    """
    Transform a `FitToHairpinDict` to one or more `pandas.DataFrame`.

    The dataframe contains one row per bead and valid hairpin. By valid one means
    a hairpin, for a given bead, which was fitted against the latter. Some hairpins
    are considered incorrect, for example if their size is inconsistent with that
    of the bead.

    As an example, if there are 2 possible hairpins and 3 beads, there should be
    from 0 to 6 rows in the dataframe. Zero would imply that none of the beads
    had a size consistent with any of the hairpins.

    Default Indexes
    ---------------

    * track: the track from which is issued a given bead
    * bead: the bead id in the track

    Default Columns
    ---------------

    * hpin:           the hairpin name.
    * cost:           the cost value for fitting the bead to that hairpin.
      This value may vary depending on which cost function was selected and its
      configuration.
    * oligo:          the oligos used for fitting, if known.
    * stretch:        the stretch value from fitting to that hairpin.
    * bias:           the bias value from fitting to that hairpin.
    * strandsize:     the sequence length
    * nbindings:      the number of expected bindings on the hairpin.
    * nblockages:     the number of blockage positions detected on the bead.
    * hfsigma:        the high frequency noise for that bead.
    * considering blockage positions versus expected bindings:
        * expnonaffected: the number of formers not assigned to any of the latters.
        * expaffected:    the number of assigned formers including duplicated formers.
        * expfalseneg:    the number of peak(s) which not appear experimently but
          assigned theoretically.
        * exptruepos:     the number of assigned formers.
        * expresiduals:   the mean distance from a former to its assigned latter.
        * expduplicates:  the number of assigned formers less the number of assigned latters.
    * considering expected bindings versus blockage positions:
        * hpinnonaffected : the number of formers not assigned to any of thelatters.
        * hpinfalseneg:     the number of latters without assignees. => ignore, No SENSE.
        * hpinaffected :    the number of assigned formers.
        * hpinresiduals:    the mean distance from a former to its assigned latter.
        * hpinduplicates:   the number of assigned formers less the number of assigned latters.
    * For identified blockage positions:
        * tpaverageduration:   the average event duration
        * tphybridisationrate: the average event rate
        * tpeventcount:        the average event count
    * For non-identified blockage positions:
        * fpaverageduration:   the average event duration
        * fphybridisationrate: the average event rate
        * fpeventcount:        the average event count

    Configuration
    -------------

    The following can be provided to the `measures` dictionnary of the task

    * aggregator: Union[str, Callable[[Sequence[float]], float]
        the aggregator to use, `np.nanmedian` by default.
    * distances: Dict[str, float]
        A dictionnary containing:
        ```python
        {
            'bead': max distance from blockage positions to an expected binding,
            'hpin': max distance from expected bindings to a blockage position.
        }
        ```
    * peaks: Union[Bool, Dict[str, Any]]
        If `peaks = True`, then an additionnal *peaks* column is added holding
        which holds a dataframe of the peaks for a given bead and hairpin. That
        dataframe has at one row per peak and columns:
            * *peakposition*
            * *hybridisationrate*
            * *averageduration*
            * *status*: either '< baseline', 'baseline' 'falsepos', 'truepos',
            'singlestrand', '> singlestrand' as needed.
            * *orientation*: the orientation of the binding oligo
            * *baseposition*: the *peakposition* in base pairs
            * *closest*: the closest theoretical position
            * *distance*: the distance to the closest theoretical position

        If *peaks* is a dictionnary, it is passed to a PeaksDataFrameFactory.
        The latter will measure statistics on true positives and false
        positives, then report the results aggregated by bead and hairpin.

            * Should the dictionnary contain `all = True`, then the previous
                *peaks* column is added.
            * If a `falseneg = True` or `missing = True` entry is added to the
                dictionnary, lines are added for each bead corresponding to
                theoretical bindings missing in the data. Irrelevant entries are
                indicated with `NaN` or `None` values.

    * optionals: Dict[str, Callable[[FitToHairpinDict, int, FitBead], np.ndarray]]
        A dictionnary for creating additional columns. The functions
        take 3 arguments, the view, the bead id, and the results for that bead.
    """
    _orientations: Dict[str, np.ndarray]

    # pylint: disable=arguments-differ
    def __init__(
            self,
            task,
            buffers,
            frame:     FitToHairpinDict,
            **kwa:     Callable[[FitToHairpinDict, int, FitBead], np.ndarray]
    ):
        super().__init__(task, buffers, frame)
        meas                               = dict(task.measures, **kwa)
        distances                          = meas.pop('distances', None)
        self.__distances: Dict[str, float] = (
            {
                i: float(cast(int, distances))
                for i in ('bead', 'hpin')
            } if np.isscalar(distances) else

            {
            } if distances is None      else

            {
                str(i): float(j)
                for i, j in dict(cast(dict, distances)).items()
            }
        )

        self.__addfalseneg = False
        if isinstance(meas.get('peaks', None), dict):
            self.__addfalseneg = sum(
                meas['peaks'].pop(i, False) for i in ('falseneg', 'missing')
            ) > 0
        self.__keeppeaks = self.__addfalseneg
        if meas.get('peaks', None) is True:
            meas.pop('peaks')
            self.__keeppeaks = True
        elif meas.get('peaks', {}).get('all', False):
            self.__keeppeaks = True
        meas.get('peaks', {}).pop('all', None)

        peaks = DataFrameTask(measures = meas.pop('peaks', {}))
        self.__peaks: PeaksDataFrameFactory = (
            PeaksDataFrameFactory(peaks, buffers, frame)
            .discardcolumns('track', 'bead')
        )

        self.__aggregator: Callable[[Sequence[float]], float] = cast(
            Callable[[Sequence[float]], float],
            self.getfunction(meas.pop('aggregator', 'median'))
        )
        self.__optionals:                                                      \
            Dict[str, Callable[[FitToHairpinDict, int, FitBead], np.ndarray]]  \
            = meas

    def _run(
            self,
            frame: FitToHairpinDict,
            bead:  int,
            res:   FitBead
    ) -> Dict[str, np.ndarray]:  # type: ignore
        self.__compute_orientation(frame)
        frame = self.__config(frame)
        fits  = frame.fits(bead, res.events)
        out   = self.__basic(frame, bead, res, fits)
        out.update(self.__complex(frame, res, fits))
        out.update({i: j(frame, bead, res) for i, j in self.__optionals.items()})

        out['oligo'] = np.empty(len(next(iter(out.values()))), dtype = f'<U{self.OSZ}')
        if isinstance(frame.config.oligos, (str, Pattern)):
            out['oligo'][:] = str(frame.config.oligos)[:self.OSZ]
        elif frame.config.oligos is not None:
            out['oligo'][:] = ','.join(str(i) for i in frame.config.oligos)[:self.OSZ]

        if fits:
            out['expfalseneg']  = out['nbindings']  - out['exptruepos']
        return out

    @staticmethod
    def __config(frame: FitToHairpinDict) -> FitToHairpinDict:
        cur   = frame
        first = None
        while hasattr(cur, 'data'):
            if isinstance(getattr(cur, 'config', None), FitToHairpinTask):
                first = cur
            cur = cur.data

        if not first:
            raise AttributeError(
                "Dataframe can only be created if a FitToHairpinTask is in the tasklist"
            )
        return cast(FitToHairpinDict, first)

    OSZ: ClassVar[int] = 30

    @staticmethod
    def __basic(
            frame: FitToHairpinDict,
            bead:  int,
            res:   FitBead,
            fits:  Dict[Optional[str], HairpinFitter]
    ) -> Dict[str, np.ndarray]:
        size = len(res.distances)
        return {
            'hpin':       np.array(list(res.distances),                    dtype = '<U20'),
            'cost':       np.array([i[0] for i in res.distances.values()], dtype = 'f4'),
            'stretch':    np.array([i[1] for i in res.distances.values()], dtype = 'f4'),
            'bias':       np.array([i[2] for i in res.distances.values()], dtype = 'f4'),
            'nbindings':  np.array([i.peaks.size for i in fits.values()],  dtype = 'i4'),
            'strandsize': np.array([i.strandsize for i in fits.values()],  dtype = 'i4'),
            'nblockages': np.full(size, len(res.events),                   dtype = 'i4'),
            'hfsigma':    np.full(size, frame.track.rawprecision(bead),    dtype = 'f4')
        }

    def __complex(
            self,
            frame: FitToHairpinTask,
            res:   FitBead,
            fits:  Dict[Optional[str], HairpinFitter],
    ) -> Dict[str, np.ndarray]:
        info: Dict[str, List[float]] = {}
        dist = res.distances
        data = self.__base_df(frame, res)
        cols = list((set(data.columns) - {'peakposition', 'status'}))
        for tpe in ('bead', 'hpin'):
            for hpin, alg in fits.items():
                window = self.__dist_complex(tpe, hpin, frame.config)
                self.__bead_hpin_complex(
                    tpe,
                    info,
                    self.__pks_complex(res, dist, hpin, alg),
                    window
                )
                if tpe != 'hpin':
                    cur = self.__peaks_df(
                        hpin, res.distances[hpin], alg.peaks, window, data
                    )
                    if self.__keeppeaks:
                        info.setdefault('peaks', []).append(cur)
                    self.__tp_fp_complex(cols, info, cur)

        out = {i: np.array(j, dtype = 'f4') for i, j in info.items() if i != 'peaks'}
        if 'peaks' in info:
            out['peaks'] = np.full(len(next(iter(out.values()))), None, dtype = 'O')
            out['peaks'][:] = info['peaks']
        return out

    @staticmethod
    def __pks_complex(res, dist, hpin, alg) -> Tuple[np.ndarray, np.ndarray]:
        return (
            (res.events['peaks']-dist[hpin][2])*dist[hpin][1],
            alg.peaks
        )

    def __dist_complex(self, tpe: str, hpin: Optional[str], config: FitToHairpinTask) -> float:
        return (
            self.__distances[tpe]       if tpe in self.__distances else
            config.match[hpin].window   if hpin in config.match    else
            config.DEFAULT_MATCH.window
        )

    def __base_df(self, frame, res) -> pd.DataFrame:
        data = pd.DataFrame(self.__peaks.dictionary(frame, (res.key, res.events)))
        data.sort_values('peakposition', inplace = True)
        data['status'] = (
            PeakStatusComputer(frame.config.baseline, frame.config.singlestrand)
            (frame, res.key, res.events)
        )
        return data

    def __peaks_df(   # pylint: disable=too-many-arguments
            self, hpin, dist, hpinpeaks, window, data
    ) -> pd.DataFrame:
        hpos = (data['peakposition'] - dist[2]) * dist[1]
        inds = np.minimum(len(hpinpeaks)-1, np.searchsorted(hpinpeaks, hpos))
        inds[
            np.abs(hpinpeaks[inds] - hpos) > np.abs(hpinpeaks[np.maximum(0, inds-1)] - hpos)
        ] -= 1

        delta  = hpinpeaks[inds] - hpos
        status = np.copy(data['status'])
        status[(status == '') & (np.abs(delta) < window)] = 'truepos'
        status[status == ''] = 'falsepos'

        closest     = hpinpeaks[inds]
        orientation = np.full(len(status), "", dtype = '<U1')

        if hpin in self._orientations:
            ori = self._orientations[hpin]
            orientation[np.isin(closest, ori["position"][ori['orientation']])]  = "+"
            orientation[np.isin(closest, ori["position"][~ori['orientation']])] = "-"

        data = data.assign(
            closest      = closest,
            distance     = delta,
            baseposition = hpos,
            status       = status,
            orientation  = orientation,
        )

        return self.__peaks_df_falseneg(hpin, data, dist)

    def __peaks_df_falseneg(self, hpin, data, dist):
        if hpin not in self._orientations or not self.__addfalseneg:
            return data

        avail  = data.closest[data.status == 'truepos'].unique()
        orient = self._orientations[hpin]
        for symb in '+-':
            arr  = orient["position"][orient['orientation'] == (symb == '+')]
            miss = np.setdiff1d(arr, avail)
            if not len(miss):
                continue

            dfmi = pd.DataFrame(dict(
                {
                    i: (
                        np.zeros(len(miss), dtype = j.dtype)
                        if any(
                            np.issubdtype(j.dtype, k)
                            for k in (np.object_, np.bool_, np.str_)
                        ) else
                        np.NaN
                    )
                    for i, j in data.items()
                },
                eventcount   = 0,
                closest      = miss,
                orientation  = symb,
                status       = 'falseneg',
                peakposition = miss/dist[1] + dist[2],
                baseposition = miss
            ))
            data = pd.concat([data, dfmi], sort = False)
        return data

    def __bead_hpin_complex(
            self,
            tpe:  str,
            out:  Dict[str, List[float]],
            arrs: Tuple[np.ndarray, np.ndarray],
            dist: float
    ) -> np.ndarray:
        left  = np.concatenate([[-1e30], arrs[tpe == "bead"], [1e30]])
        right = arrs[tpe != "bead"]
        inds  = np.searchsorted(left, right)
        inds[left[inds]-right > right-left[inds-1]] -= 1

        good  = np.abs(left[inds]-right) < dist
        ids   = inds[good]-1

        if tpe == "bead":
            tpe = "exp"
        out.setdefault(tpe+'affected',    []).append(np.array(good.sum(), dtype = 'i4'))
        out.setdefault(tpe+'nonaffected', []).append(good.size - good.sum())
        out.setdefault(tpe+'duplicates',  []).append(good.size - np.unique(ids).size)
        out.setdefault(tpe+'truepos',     []).append(np.unique(ids).size)
        out.setdefault(tpe+'residuals',   []).append(
            self.__aggregator(
                np.abs(arrs[tpe == 'exp'][ids]-arrs[tpe != 'exp'][good]) ** 2
            )
        )

    def __tp_fp_complex(  # py
            self,
            cols:   List[str],
            out:    Dict[str, List[float]],
            data:   pd.DataFrame,
    ):
        for fmt in ('tp', 'fp'):
            tmp = data.loc[
                data['status'] == ('truepos' if fmt == 'tp' else 'falsepos'),
                cols
            ]
            if tmp.shape[0]:
                for i, j in tmp.iteritems():
                    out.setdefault(fmt+i, []).append(self.__aggregator(j))
            else:
                for i, j in tmp.iteritems():
                    out.setdefault(fmt+i, []).append(np.NaN)

    def __compute_orientation(self, frame):
        if hasattr(self, '_orientations'):
            return
        self._orientations = {}
        task = frame.config
        if task.oligos and task.sequences:
            task = frame.config.resolve(frame.track.path)
        if task.oligos and task.sequences:
            self._orientations = {
                i: j for i, j in _peaks(task.sequences, task.oligos) if i in task.fit
            }
