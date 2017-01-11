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

@fromstream
def read(stream:TextIO) -> 'Iterator[Tuple[str,str]]':
    u"reads a path and yields pairs (name, sequence)"
    yield from seqio.FastaIO.SimpleFastaParser(stream)

def peaks(seq:str, oligs:'Sequence[str]') -> np.ndarray:
    u"""
    Returns the peak positions and orientation associated to a sequence.
    
    A peak position is the end position of a match. With indexes starting at 0,
    that's the indexe of the first base *after* the match.
    
    The orientation is *True* if the oligo was matched and false otherwise. Palindromic
    cases are *True*.

    Matches are **case sensitive**.

    Example:

    >>> import numpy as np
    >>> seq   = "atcgATATATatcgCCCaaGGG"
    >>> peaks = peaks(seq, ('ATAT', 'CCC'))
    >>> assert len(peaks) == 4
    >>> assert all(a == b for a, b in zip(peaks['position'],    [8, 10, 17, 22]))
    >>> assert all(a == b for a, b in zip(peaks['orientation'], [True]*3+[False]))
    """
    def _get(elems, state):
        reg = re.compile('|'.join(elems))
        val = reg.search(seq, 0)
        while val is not None:
            yield (val.end(), state)
            val = reg.search(seq, val.start()+1)

    vals = dict(_get((str(Seq(i).reverse_complement()) for i in oligs), False))
    vals.update(_get((i for i in oligs), True))

    return np.fromiter(sorted(vals.items()),
                       dtype = [('position', np.int32), ('orientation', np.bool8)],
                       count = len(vals))
