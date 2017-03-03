#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"All sequences-related stuff"
from    typing import (Sequence, Union,  # pylint: disable=unused-import
                       Iterator, Tuple, TextIO)
import  pathlib
import  re
import  numpy       as np
import  Bio.SeqIO   as seqio
from    Bio.Seq     import Seq
from    utils       import fromstream

@fromstream('r')
def read(stream:TextIO) -> 'Iterator[Tuple[str,str]]':
    u"reads a path and yields pairs (name, sequence)"
    yield from seqio.FastaIO.SimpleFastaParser(stream)

PEAKS_DTYPE = [('position', 'i4'), ('orientation', np.bool8)]
PEAKS_TYPE  = Sequence[Tuple[int, bool]]
def peaks(seq:str, oligs:'Union[Sequence[str], str]', flags = re.IGNORECASE) -> np.ndarray:
    u"""
    Returns the peak positions and orientation associated to a sequence.

    A peak position is the end position of a match. With indexes starting at 0,
    that's the indexe of the first base *after* the match.

    The orientation is *True* if the oligo was matched and false otherwise. Palindromic
    cases are *True*.

    Matches are **case sensitive**.

    Example:

        >>> import numpy as np
        >>> seq = "atcgATATATatcgCCCaaGGG"
        >>> res = peaks(seq, ('ATAT', 'CCC'))
        >>> assert len(res) == 4
        >>> assert all(a == b for a, b in zip(res['position'],    [8, 10, 17, 22]))
        >>> assert all(a == b for a, b in zip(res['orientation'], [True]*3+[False]))
        >>> res = peaks(seq, 'ATAT')
        >>> assert len(res) == 2
        >>> assert all(a == b for a, b in zip(res['position'],    [8, 10]))
        >>> assert all(a == b for a, b in zip(res['orientation'], [True]*2))

    """
    if isinstance(oligs, str):
        oligs = (oligs,)

    if len(oligs) == 0:
        return np.empty((0,), dtype = PEAKS_TYPE)

    def _get(elems, state):
        reg = re.compile('|'.join(elems), flags)
        val = reg.search(seq, 0)
        while val is not None:
            yield (val.end(), state)
            val = reg.search(seq, val.start()+1)

    vals = dict(_get((str(Seq(i).reverse_complement()) for i in oligs), False))
    vals.update(_get((i for i in oligs), True))

    return np.array(sorted(vals.items()), dtype = PEAKS_DTYPE)

def overlap(ol1:str, ol2:str, minoverlap = None):
    u"""
    Returns wether the 2 oligos overlap

    Example:

        >>> import numpy as np
        >>> assert  not overlap('ATAT', '')
        >>> assert  overlap('ATAT', 'ATAT')
        >>> assert  overlap('ATAT', 'CATA')
        >>> assert  overlap('ATAT', 'CCAT')
        >>> assert  overlap('ATAT', 'CCCA')
        >>> assert  overlap('ATAT', 'ATAT', minoverlap = 4)
        >>> assert  overlap('ATAT', 'CATA', minoverlap = 3)
        >>> assert  overlap('ATAT', 'CCAT', minoverlap = 2)
        >>> assert  overlap('ATAT', 'CCCA', minoverlap = 1)
        >>> assert  not overlap('ATAT', 'ATAT', minoverlap = 5)
        >>> assert  not overlap('ATAT', 'CATA', minoverlap = 4)
        >>> assert  not overlap('ATAT', 'CCAT', minoverlap = 3)
        >>> assert  not overlap('ATAT', 'CCCA', minoverlap = 2)

        >>> assert  not overlap('', 'ATAT')
        >>> assert  overlap('ATAT', 'ATAT')
        >>> assert  overlap('CATA', 'ATAT')
        >>> assert  overlap('CCAT', 'ATAT')
        >>> assert  overlap('CCCA', 'ATAT')
        >>> assert  overlap('ATAT', 'ATAT', minoverlap = 4)
        >>> assert  overlap('CATA', 'ATAT', minoverlap = 3)
        >>> assert  overlap('CCAT', 'ATAT', minoverlap = 2)
        >>> assert  overlap('CCCA', 'ATAT', minoverlap = 1)
        >>> assert  not overlap('ATAT', 'ATAT', minoverlap = 5)
        >>> assert  not overlap('CATA', 'ATAT', minoverlap = 4)
        >>> assert  not overlap('CCAT', 'ATAT', minoverlap = 3)
        >>> assert  not overlap('CCCA', 'ATAT', minoverlap = 2)

    """
    if len(ol1) < len(ol2):
        ol1, ol2 = ol2, ol1

    if minoverlap is None or minoverlap <= 0:
        minoverlap = 1

    if minoverlap > len(ol2):
        return False

    rng = range(minoverlap, len(ol2))
    if ol2 in ol1:
        return True
    return any(ol1.endswith(ol2[:i]) or ol1.startswith(ol2[-i:]) for i in rng)
