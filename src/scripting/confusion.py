#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compute confusion matrix using the experiments and the real sequence"
from   inspect        import getmembers
from   typing         import (Union, List, Sequence, Iterator, Tuple, Any,
                              Iterable, NamedTuple, Optional)
import numpy          as np
import pandas         as pd

from   scipy.stats    import percentileofscore

from   sequences      import LNAHairpin, Strand, peaks as _peaks, Translator

from   utils          import initdefaults

def trackoligo(name:str, oligos: Sequence[str], reference = 'OR3') -> str:
    "returns the oligo associated to a track"
    lst  = {oli for oli in oligos if oli.upper() in name.upper()}
    if not lst:
        raise KeyError(f"Can not find the oligo corresponding to track {name}"
                       " in the set of oligos {oligos}")

    if len(lst) == 1 and next(iter(lst)) == reference:
        return reference

    lst.discard(reference)
    return next(i for i in oligos if i in lst)

def oligopeaks(oligo: Union[str, Iterable[str]], seq: LNAHairpin,
               withref      = True,
               hpname: str  = None,
               delta        = (30, 41)) -> Tuple[np.ndarray, np.ndarray]:
    """
    compute the list of theoretical peaks for oligo
    input: oligo is a string
    seq is a theoretical object
    'full': string with the full sequence
    'target': string with the target sequence
    'oligo': string with the reference oligo
    withref is True if we output the peaks of the reference oligo
    False if not
    """
    #reverse complement of oligo
    #find the positions and orientations of oli in the full sequence
    if isinstance(oligo, str):
        oli = _peaks(seq.full, Translator.reversecomplement(oligo))
    else:
        oli = _peaks(seq.full, [Translator.reversecomplement(i) for i in oligo])

    #keep the positions in target
    if hpname and seq.target != seq.full:
        fulls = _peaks(seq.full, seq.target)['position'][0]
        rng   = fulls-len(seq.target)-delta[0], fulls + delta[1]
        oli   = oli[(oli['position'] >= rng[0]) & (oli['position'] <= rng[1])]

    #if withref then return array of all peaks of the reference and the peaks of oligo
    if withref:
        ref = _peaks(seq.full, seq.references)
        oli = np.sort(np.append(oli, ref[ref['orientation']]))

    return (oli['position'][oli['orientation']], oli['position'][~oli['orientation']])

class ConfusionMatrix:
    """
    Arguments required to create a confusion matrix
    """
    oligos: List[str] = []
    seq               = LNAHairpin()
    ioc               = 1
    tolerance         = 0.01, 0.01
    rule              = 'theoretical_interval'
    brother           = 3
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def detection(self, data:pd.DataFrame, **kwa) -> pd.DataFrame:
        "returns the detection dataframe"
        return DetectionFrameCreator.dataframe(self, data, **kwa)

    def confusion(self, data:pd.DataFrame, **kwa) -> 'LNAHairpinDataFrameResults':
        "returns the detection dataframe"
        return LNAHairpinDataFrameCreator.results(self, data, **kwa)

class DataFrameCreator(ConfusionMatrix):
    "Creates dataframes"
    theo: np.ndarray
    def __init__(self, config):
        super().__init__(**config.__dict__)

    @classmethod
    def dataframe(cls, config: ConfusionMatrix, data: pd.DataFrame, **kwa) -> pd.DataFrame:
        "returns a dataframe for all tracks"
        size = -len('column')
        out  = tuple(tuple(i) for i in cls.iterate(config, data, **kwa))
        data = {j[:size]: [k[i] for k in out]
                for i, (j,_) in enumerate(cls._columns(cls))}
        return pd.DataFrame(data)

    @staticmethod
    def _columns(itm):
        return (i for i in getmembers(itm) if i[0].endswith('column') and callable(i[1]))

    def groupbyiterate(self, data: pd.core.groupby.DataFrameGroupBy
                      ) -> Iterator[Iterator]:
        "iterates over the provided groupby"
        cols = [i for _, i in self._columns(self)]
        return ((fcn(*self.lineargs(info)) for fcn in cols) for info in data)

    @classmethod
    def iterate(cls, config: ConfusionMatrix, data: pd.DataFrame, **_):
        """
        iterates over all lines
        """
        raise NotImplementedError()

    def lineargs(self, info:Tuple[Any, pd.DataFrame]):
        """
        returns args needed by column methods
        """
        raise NotImplementedError()

class DetectionFrameCreator(DataFrameCreator):
    """
    Creates the detection dataframe
    """
    def __init__(self, config, trackname:str, strand: Strand, hptarget: str) -> None:
        super().__init__(config)
        self.trackname  = trackname
        self.oligoname  = next(i for i in self.oligos if i.upper() in trackname.upper())
        self.strand     = Strand(strand)
        theo            = oligopeaks(trackoligo(trackname, self.oligos),
                                     self.seq, hptarget)
        strands         = np.arange(2)[::(1 if strand.value else -1)]
        self.doublebind = np.min(np.abs(theo[strands[0]].T - theo[strands[1]][:, None]),
                                 axis = 0) < self.brother
        self.theo       = theo[strands[0]]

    # pylint: disable=arguments-differ
    @classmethod
    def iterate(cls, # type: ignore
                config: ConfusionMatrix, data: pd.DataFrame,
                hptarget = 'target') -> Iterator[Iterator]:
        """
        iterates over all lines
        """
        tracks = data.reset_index().track.unique()
        data   = data.reset_index().set_index('track')
        for trk in tracks:
            grp = data.loc[trk].groupby('peakposition')
            yield from cls(config, trk, Strand.positive, hptarget).groupbyiterate(grp)
            yield from cls(config, trk, Strand.negative, hptarget).groupbyiterate(grp)

    def lineargs(self, info:Tuple[float, pd.DataFrame]) -> Tuple[int, float, pd.DataFrame]:
        """
        returns args needed by column methods
        """
        idtheo  = np.searchsorted(self.theo, info[0])
        return (idtheo + np.argmin(np.abs(self.theo[idtheo:idtheo+1]-info[0])),
                info[0], info[1])

    def rulecolumn(self, *_) -> str:
        "the rule name"
        return self.rule

    def trackcolumn(self, *_) -> str:
        "the track name"
        return self.trackname

    def oligocolumn(self, *_) -> str:
        "the oligo name"
        return self.oligoname

    def theoposcolumn(self, idtheo: int, *_) -> int:
        "the theoretical positions in bases"
        return self.theo[idtheo]

    def strandcolumn(self, *_) -> str:
        "the strand name"
        return self.strand.name

    def totalpeakscolumn(self, *_) -> int:
        "the number of theoretical peaks on the current strand"
        return len(self.theo)

    @staticmethod
    def expposcolumn(_, exppos: float, *__) -> float:
        "the experimental positions in µm"
        return exppos

    @staticmethod
    def peaknbcolumn(idtheo: int, *_) -> int:
        "the index of the theoretical peak on the current strand"
        return idtheo

    def distcolumn(self, idtheo:int, exppos:float, _) -> float:
        "the experimental distance from the theory"
        return exppos-self.theo[idtheo]

    def doublebindingcolumn(self, idtheo: int, *_) -> bool:
        "whether there could be a binding on both strands at the same time"
        return self.doublebind[idtheo]

    def detectioncolumn(self, idtheo: int, _, group:pd.DataFrame) -> bool:
        "whether there could be a binding on both strands at the same time"
        avg  = group.avg.values
        theo = self.theo[idtheo]
        return ((percentileofscore(avg,  theo - self.ioc)
                 -percentileofscore(avg, theo + self.ioc))*1e-2
                >= self.tolerance[int(self.strand.value)])

    @staticmethod
    def hybratecolumn(_, __, group:pd.DataFrame) -> float:
        "whether there could be a binding on both strands at the same time"
        return group.hybridisationrate.values[0]

    @staticmethod
    def hybtimecolumn(_, __, group:pd.DataFrame) -> float:
        "whether there could be a binding on both strands at the same time"
        return group.averageduration.values[0]

class LNAHairpinDataFrameResults(NamedTuple):
    data      : pd.DataFrame
    confusion : pd.DataFrame
    truepos   : int
    falsepos  : int
    trueneg   : int
    falseneg  : int

class LNAHairpinDataFrameCreator(DataFrameCreator):
    "creates detailed dataframe"
    def __init__(self, config,
                 references: Union[str, List[str]] = None,
                 strand                            = Strand.positive) -> None:
        super().__init__(config)
        if references is None:
            references  = self.seq.references
        self.references = (oligopeaks(references, self.seq) # type: ignore
                           [0 if strand.value else 1])

    @classmethod
    def iterate(cls, # type: ignore # pylint: disable=arguments-differ
                config: ConfusionMatrix, data: pd.DataFrame,
                **kwa) -> Iterator[Iterator]:
        """
        iterates over all lines
        """
        yield from cls(config, **kwa).groupbyiterate(data.groupby(['theopos', 'track']))

    @classmethod
    def results(cls, config: ConfusionMatrix, data: pd.DataFrame,
                confusionindex   = 'confusionstate',
                confusioncolumns = ('count',),
                **kwa) -> LNAHairpinDataFrameResults:
        """
        creates and returns all results
        """
        data      = cls.dataframe(config, data, **kwa)
        confusion = pd.crosstab(index   = data[confusionindex],
                                columns = list(confusioncolumns))
        def _count(name):
            try:
                return confusion.loc[name]['count']
            except KeyError:
                return 0
        counts = (_count(i) for i in ('FN', 'FP', 'TN', 'TP'))
        return LNAHairpinDataFrameResults(data, confusion, *counts)

    @staticmethod
    def lineargs(info:Tuple[Tuple[float, str], pd.DataFrame]) -> Tuple[float, str, pd.DataFrame]:
        """
        returns args needed by column methods
        """
        return info[0][0], info[0][1], info[1]

    @staticmethod
    def trackcolumn(_, track:str, *__) -> str:
        "the track name"
        return track

    @staticmethod
    def theoposcolumn(theopos: int, *_) -> int:
        "the theoretical positions in bases"
        return theopos

    @staticmethod
    def expposcolumn(_, __, grp: pd.DataFrame) -> Optional[float]:
        "the experimental positions in µm"
        try:
            return grp.exppos[grp.detection].first
        except IndexError:
            return None

    @staticmethod
    def oligocolumn(_, __, grp: pd.DataFrame) -> str:
        "the oligo name"
        return grp.oligo.values[0]

    @staticmethod
    def strandcolumn(_, __, grp: pd.DataFrame) -> str:
        "the strand name"
        return grp.strand.values[0]

    @staticmethod
    def confusionstatecolumn(_, __, grp: pd.DataFrame) -> str:
        "returns the state of the peak : false/true positive/negative"
        state = np.any(grp.detection)
        if Strand(grp.strand.values[0]).value:
            return 'TP' if state else 'FN'

        if state:
            hasdouble = np.any(grp[['detection', 'doublebinding']].sum(axis=1).isin([2]))
            return 'TN' if hasdouble else 'FP'
        return 'TN'

    @staticmethod
    def goodestimatorscolumn(_, __, grp: pd.DataFrame) -> int:
        "returns the number of good estimators"
        cnt = grp.detection.sum()
        return cnt if Strand(grp.strand.values[0]).value else len(grp) - cnt

    @staticmethod
    def estimatorscolumn(_, __, grp: pd.DataFrame) -> int:
        "returns the number of good estimators"
        return len(grp)

    def isrefcolumn(self, pos: int, *_) -> bool:
        "returns the number of good estimators"
        return pos in self.references
