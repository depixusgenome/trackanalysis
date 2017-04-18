#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All sequences-related stuff"
from    typing import (Sequence, Union,  # pylint: disable=unused-import
                       Iterator, Tuple, TextIO)
import  pathlib
import  re
import  numpy       as np
from    Bio.Seq     import Seq
from    utils       import fromstream

@fromstream('r')
def read(stream:TextIO) -> 'Iterator[Tuple[str,str]]':
    "reads a path and yields pairs (name, sequence)"
    title = None
    seq   = ""
    ind   = 0
    for line in stream:
        line = line.strip()
        if len(line) == 0:
            continue

        if line[0] == '#':
            continue

        if line[0] == '>':
            if len(seq):
                yield ("hairpin %d" % ind if title is None else title, seq)
                ind += 1

            title = line[1:].strip()
            seq   = ''
            continue
        else:
            seq += line

    if len(seq):
        yield ("hairpin %d" % ind if title is None else title, seq)

PEAKS_DTYPE = [('position', 'i4'), ('orientation', np.bool8)]
PEAKS_TYPE  = Sequence[Tuple[int, bool]]
def _translate(olig):
    olig = olig.lower()
    for vals in (('k', '[gt]'), ('m', '[ac]'), ('r', '[ag]'),
                 ('y', '[ct]'), ('s', '[cg]'), ('w', '[at]'),
                 ('b', '[^a]'), ('v', '[^t]'), ('h', '[^g]'),
                 ('d', '[^c]'), ('n', '.'),    ('x', '.'),
                 ('u', 't')):
        olig = olig.replace(*vals)
    return olig

def peaks(seq:str, oligs:'Union[Sequence[str], str]', flags = re.IGNORECASE) -> np.ndarray:
    """
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
        >>> seq = "c"*5+"ATC"+"g"*5+"TAG"+"c"*5
        >>> res = peaks(seq, 'wws')
        >>> assert len(res) == 4
    """
    if isinstance(oligs, str):
        oligs = (oligs,)

    if len(oligs) == 0:
        return np.empty((0,), dtype = PEAKS_DTYPE)


    def _get(elems, state):
        reg = re.compile('|'.join(_translate(i) for i in elems), flags)
        val = reg.search(seq, 0)
        while val is not None:
            yield (val.end(), state)
            val = reg.search(seq, val.start()+1)

    vals = dict(_get((str(Seq(i).reverse_complement()) for i in oligs), False))
    vals.update(_get((i for i in oligs), True))

    return np.array(sorted(vals.items()), dtype = PEAKS_DTYPE)

def marksequence(seq:str, oligs: Sequence[str]) -> str:
    u"Returns a sequence with oligos to upper case"
    seq = seq.lower()
    for olig in oligs:
        seq  = seq.replace(olig.lower(), olig.upper())

        olig = str(Seq(olig).reverse_complement())
        seq  = seq.replace(olig.lower(), olig.upper())
    return seq

def overlap(ol1:str, ol2:str, minoverlap = None):
    """
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
