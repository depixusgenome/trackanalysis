#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"All sequences-related stuff"
from    typing import (Sequence, Union,  # pylint: disable=unused-import
                       Iterator, Tuple, TextIO)
import  pathlib
import  numpy       as np
import  Bio.SeqIO   as seqio
from    Bio.Seq     import Seq
from    utils       import fromstream

@fromstream
def read(stream:TextIO) -> 'Iterator[Tuple[str,np.ndarray]]':
    u"reads a path and yields pairs (name, sequence)"
    yield from ((name, np.array(val, dtype = '<U4'))
                for name, val in seqio.FastaIO.SimpleFastaParser(stream))

def peaks(seq:str, oligs:'Sequence[str]') -> np.ndarray:
    u"returns the peaks associated to a sequence"
    sequence = np.array(seq, dtype = '<U4', copy = False)

    def _get(elems, state):
        for olig in elems:
            nol  = len(olig)
            nseq = (len(sequence)//nol)*nol
            for i in range(nol):
                vals = sequence[i:i+nseq].reshape((nseq//nol,nol)) == olig
                yield from ((j+1, state) for j in np.nonzero(vals)[0])

    vals = dict(_get((str(Seq(i).reverse_complement()) for i in oligs), False))
    vals.update(_get((i for i in oligs), True))

    return np.array(vals.items(),
                    dtype = [('position', np.int32), ('orientation', np.bool8)])
