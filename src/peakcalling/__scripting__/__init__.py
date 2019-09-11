#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating FitToHairpinDict for scripting purposes"
from   pathlib                          import Path
from   typing                           import (
    List, Union, Iterator, Callable, Dict, Iterable, Optional
)

from   data                             import Track
from   data.tracksdict                  import TracksDict
from   data.__scripting__.dataframe     import adddataframe
from   peakfinding.__scripting__        import (Detailed,
                                                PeaksTracksDictOperator as _PTDO)
from   taskmodel.__scripting__          import Tasks, Task
from   utils.decoration                 import addto
from   ..toreference                    import HistogramFit, ChiSquareHistogramFit
from   ..processor.fittohairpin         import (
    FitToHairpinDict, FitToHairpinTask, Oligos, Sequences
)
from   ..processor                      import FitToReferenceDict, FitToReferenceTask

@addto(FitToReferenceTask)
def __scripting_save__(self):
    self.fitdata.clear()

def _fit(self, tpe, sequence, oligos, kwa):
    "computes hairpin fits"
    if sequence is not None:
        kwa['sequences'] = sequence
    if oligos is not None:
        kwa['oligos']    = oligos

    last  = getattr(Tasks, tpe)(**kwa)
    if not last.fit and  last.oligos not in ['3mer', 'kmer', '4mer', '5mer']:
        raise IndexError('No fit found')
    return self.apply(*Tasks.defaulttasklist(self, Tasks.peakselector), last)

@addto(Track)
def fittohairpin(
        self,
        sequence: Sequences,
        oligos: Oligos = 'kmer',
        **kwa
) -> FitToHairpinDict:
    """
    Computes hairpin fits.

    Arguments are for creating the FitToHairpinTask. By default, we try to
    detect a kmer in the track name.

    Parameters
    ----------
    sequence:
        One or more sequence or the path to a fasta file
    oligos:
        One or more oligos or the pattern with which to parse the track file
        names.  It can also be 'kmer', '3mer' or '4mer' in which case the track
        files are parsed in order to find a kmer, a 3mer or a 4mer.
    kwa:
        values for the FitToHairpinTask attributes
    """
    return _fit(self, 'fittohairpin', sequence, oligos, kwa)

@addto(Track)
def fittoreference(self, task: FitToReferenceTask = None, **kwa) -> FitToReferenceDict:
    """
    Computes fits to a reference.

    Arguments are for creating the FitToReferenceTask.
    """
    if task is not None and len(kwa):
        raise NotImplementedError()
    return self.apply(*Tasks.defaulttasklist(self, Tasks.peakselector),
                      (task if isinstance(task, FitToReferenceTask) else
                       FitToReferenceTask(**kwa)))

@addto(Track)
def beadsbyhairpin(
        self,
        sequence: Sequences,
        oligos: Oligos = 'kmer',
        **kwa
):
    """
    Computes hairpin fits, sorted by best hairpin.

    Arguments are for creating the FitToHairpinTask. By default, we try to
    detect a kmer in the track name.

    Parameters
    ----------
    sequence:
        One or more sequence or the path to a fasta file
    oligos:
        One or more oligos or the pattern with which to parse the track file
        names.  It can also be 'kmer', '3mer' or '4mer' in which case the track
        files are parsed in order to find a kmer, a 3mer or a 4mer.
    kwa:
        values for the FitToHairpinTask attributes
    """
    return _fit(self, 'beadsbyhairpin', sequence, oligos, kwa)

@addto(FitToReferenceDict)
def detailed(self, ibead, precision: float = None) -> Union[Iterator[Detailed], Detailed]:
    "detailed output from config"
    if ibead is Ellipsis:
        return iter(self.detailed(i, precision) for i in self.keys())
    if isinstance(ibead, Iterable):
        return iter(self.detailed(i, precision) for i in set(self.keys) & set(ibead))
    if isinstance(self.data, FitToReferenceDict):
        if self.actions:
            raise NotImplementedError()
        return self.data.detailed(ibead, precision)  # type: ignore

    dtl  = self.data.detailed(ibead, precision)
    out  = self[...].withdata({ibead: dtl.output}).compute(ibead)
    dtl.setparams(out.params)
    return dtl

class PeaksTracksDictOperator(_PTDO, peaks = TracksDict):
    "Add dataframe method to tracksdict"
    def dataframe(  # pylint: disable=arguments-differ
            self,
            *tasks:    Union[Tasks, Task],
            transform: Optional[Callable]                     = None,
            assign:    Optional[Dict[str, Callable]]          = None,
            sequence:  Union[str, Path, None, Dict[str, str]] = None,
            oligos:    Union[str, Iterable[str], None]        = None,
            **kwa
    ):
        """
        Concatenates all dataframes obtained through *track.peaks.dataframe*

        See documentation in *track.peaks.dataframe* for other options
        """
        if sequence is None:
            sequence = kwa.pop("sequences", None)
        if oligos is None:
            oligos   = kwa.pop("oligo", None)
        if sequence:
            opts  = {
                'fit', 'constraints', 'match', 'pullphaseratio', 'singlestrand', 'baseline'
            }
            tasks = (
                *tasks,
                Tasks.fittohairpin(
                    sequences = sequence,
                    oligos    = 'kmer' if oligos is None else oligos,
                    **{i: kwa.pop(i) for i in opts & set(kwa)}
                )
            )

        tracks = self._dictview()
        if self._reference is not None:
            if not any(Tasks(i) == Tasks.fittoreference for i in tasks):
                pks    = self._items[self._reference].peaks
                if self._beads:
                    pks = pks[list(self._beads)]

                if tasks and isinstance(tasks[-1], Tasks.fittohairpin().__class__):
                    tasks = (*tasks[:-1], Tasks.fittoreference(peaks = pks), tasks[-1])
                else:
                    tasks = (*tasks, Tasks.fittoreference(peaks = pks))

            if self._reference in tracks:
                tracks = tracks[f'~{self._reference}']
        return tracks.dataframe(Tasks.peakselector, *tasks,
                                transform = transform,
                                assign    = assign,
                                **kwa)


adddataframe(FitToHairpinDict, FitToReferenceDict)
__all__: List[str] = ['HistogramFit', 'ChiSquareHistogramFit', 'FitToReferenceTask',
                      'FitToHairpinTask']
