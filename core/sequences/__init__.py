#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All sequences-related stuff"
from    enum        import Enum
from    pathlib     import Path
from    typing      import (Sequence, Union, Iterator, Tuple, TextIO, Dict,
                            List, Iterable, cast)
import  re
import  numpy       as np
from    utils       import fromstream, initdefaults, updatecopy

def _read(stream:TextIO) -> Iterator[Tuple[str,str]]:
    "reads a path and yields pairs (name, sequence)"
    title = None
    seq   = ""
    ind   = 0
    first = True
    for line in stream:
        line = line.strip()
        if len(line) == 0:
            continue

        if line[0] == '#':
            continue

        if line[0] == '>':
            if len(seq):
                first = False
                yield ("hairpin %d" % (ind+1) if title is None else title, seq)
                ind += 1

            title = line[1:].strip()
            seq   = ''
            continue
        else:
            seq += line

    if len(seq):
        if first and title is None and getattr(stream, 'name', None) is not None:
            yield (Path(str(stream.name)).stem, seq)
        else:
            yield ("hairpin %d" % (ind+1) if title is None else title, seq)

def read(stream:Union[Path, str, Dict[str,str], TextIO]) -> Iterator[Tuple[str,str]]:
    "reads a path and yields pairs (name, sequence)"
    if isinstance(stream, dict):
        return cast(Iterator[Tuple[str, str]], stream.items())

    if isinstance(stream, Iterator):
        return cast(Iterator[Tuple[str, str]], stream)

    if isinstance(stream, str) and '/' not in stream and '.' not in stream:
        try:
            if not Path(stream).exists():
                return iter((('hairpin 1', stream),))
        except OSError:
            return iter((('hairpin 1', stream),))

    return _read(cast(TextIO, open(cast(str, stream))))

PEAKS_DTYPE = [('position', 'i4'), ('orientation', 'bool')] # pylint: disable=invalid-name
PEAKS_TYPE  = Sequence[Tuple[int, bool]]                    # pylint: disable=invalid-name

class Translator:
    "Translates a sequence to peaks"
    __START  = "'", '0', 'start', 'first', 'zero', 'doublestrand', 'closed'
    __END    = '_', 'singlestrand', '$', '-1', 'last', 'end', 'open'
    __SYMBOL = '!'
    __METHS  = ((re.compile('.'+__SYMBOL), lambda x: '('+x.string[x.start()]+')'),
                (re.compile(__SYMBOL+'.'), lambda x: '('+x.string[x.end()-1]+')'))
    __TRANS  = {'k': '[gt]', 'm': '[ac]', 'r': '[ag]', 'y': '[ct]', 's': '[cg]',
                'w': '[at]', 'b': '[^a]', 'v': '[^t]', 'h': '[^g]', 'd': '[^c]',
                'n': '.',    'x': '.', 'u': 't'}
    __TRANS.update({i.upper(): j for i, j in __TRANS.items()})

    __TRAFIND = re.compile('['+''.join(__TRANS)+']')
    __ALPHABET= 'atgc'+''.join(__TRANS)+__SYMBOL+__END[0]+__START[0]
    __SPLIT   = re.compile((r'(?:[^%(alph)s]*)([%(alph)s]+)(?:[^%(alph)s]+|$)*'
                            % dict(alph =__ALPHABET)), re.IGNORECASE)

    __COMPLE  = {'a': 't', 't': 'a', 'c': 'g', 'g': 'c', 'w': 'w', 's': 's',
                 'k': 'm', 'm': 'k', 'r': 'y', 'y': 'r', 'b': 'v', 'v': 'b',
                 'h': 'd', 'd': 'h', 'n': 'n', 'x': 'x', 'u': 'a'}
    __COMPLE.update({i.upper(): j.upper() for i, j in __COMPLE.items()})
    @classmethod
    def __trarep(cls, item):
        return cls.__TRANS[item.string[slice(*item.span())]]

    @classmethod
    def __translate(cls, olig, state):
        if not state:
            olig = cls.reversecomplement(olig)
        if cls.__SYMBOL in olig:
            olig = cls.__METHS[state][0].sub(cls.__METHS[state][1], olig)
        return cls.__TRAFIND.sub(cls.__trarep, olig)

    @classmethod
    def reversecomplement(cls, oligo: str) -> str:
        "returns the reverse complement for that oligo"
        return ''.join(cls.__COMPLE.get(i, i) for i in oligo[::-1])

    @classmethod
    def __get(cls, state, seq, oligs, flags):
        for oli in oligs:
            if oli == cls.__START[1]:
                if state:
                    yield (0, state)
                continue

            if oli == cls.__END[1]:
                if state:
                    yield (len(seq), state)
                continue

            patt = cls.__translate(oli, state)
            reg  = re.compile(patt, flags)
            val  = reg.search(seq, 0)

            cnt  = range(1, patt.count('(')+1)
            if '(' in patt:
                while val is not None:
                    spans = [val.span(i)[-1] for i in cnt]
                    yield from ((i, state) for i in spans if i > 0)
                    val = reg.search(seq, val.start()+1)
            else:
                while val is not None:
                    yield (val.end(), state)
                    val = reg.search(seq, val.start()+1)

    @classmethod
    def peaks(cls, seq:Union[str, Path], oligs:Union[Sequence[str], str],
              flags = re.IGNORECASE) -> np.ndarray:
        """
        Returns the peak positions and orientation associated to a sequence.

        A peak position is the end position of a match. With indexes starting at 0,
        that's the indexe of the first base *after* the match.

        The orientation is *True* if the oligo was matched and false otherwise. Palindromic
        cases are *True*.

        Matches are **case sensitive**.

        Example:

        ```python
        import numpy as np
        seq = "atcgATATATgtcgCCCaaGGG"

        res = peaks(seq, ('ATAT', 'CCC'))
        assert len(res) == 4
        assert all(a == b for a, b in zip(res['position'],    [8, 10, 17, 22]))
        assert all(a == b for a, b in zip(res['orientation'], [True]*3+[False]))

        res = peaks(seq, 'ATAT')
        assert len(res) == 2
        assert all(a == b for a, b in zip(res['position'],    [8, 10]))
        assert all(a == b for a, b in zip(res['orientation'], [True]*2))

        seq = "c"*5+"ATC"+"g"*5+"TAG"+"c"*5
        res = peaks(seq, 'wws')
        assert len(res) == 4
        ```
        """
        ispath = False
        if isinstance(oligs, (dict, Path)):
            seq, oligs = oligs, seq

        if isinstance(oligs, str):
            oligs = cls.split(oligs)

        if isinstance(seq, dict):
            return ((i, cls.peaks(j, oligs)) for i, j in seq.items())

        ispath = isinstance(seq, Path)
        if (
                isinstance(seq, str)
                and any(i in seq for i in '/.\\')
                and len(seq) <= 1024
        ):
            try:
                ispath = Path(seq).exists()
            except OSError:
                pass

        if ispath:
            return ((i, cls.peaks(j, oligs)) for i, j in read(seq))

        if len(oligs) == 0:
            return np.empty((0,), dtype = PEAKS_DTYPE)

        vals  = dict() # type: Dict[int, bool]
        vals.update(cls.__get(False, seq, oligs, flags))
        vals.update(cls.__get(True, seq, oligs, flags))
        return np.array(sorted(vals.items()), dtype = PEAKS_DTYPE)

    @classmethod
    def split(cls, oligs:str)->Sequence[str]:
        "splits a string of oligos into a list"
        for i in cls.__START[1:]:
            oligs = oligs.replace(i, cls.__START[0]).replace(i.upper(), cls.__START[0])
        for i in cls.__END[1:]:
            oligs = oligs.replace(i, cls.__END[0]).replace(i.upper(), cls.__END[0])
        out   = sorted(i.lower() for i in cls.__SPLIT.findall(oligs))
        return [cls.__END[1]    if i == cls.__END[0]   else
                cls.__START[1]  if i == cls.__START[0] else
                i for i in out]

peaks       = Translator.peaks # pylint: disable=invalid-name
splitoligos = Translator.split # pylint: disable=invalid-name

def marksequence(seq:str, oligs: Sequence[str]) -> str:
    u"Returns a sequence with oligos to upper case"
    seq = seq.lower()
    for olig in oligs:
        seq  = seq.replace(olig.lower(), olig.upper())

        olig = Translator.reversecomplement(olig)
        seq  = seq.replace(olig.lower(), olig.upper())
    return seq

def markedoligos(oligos: Sequence[str]) -> Dict[str, str]:
    "Return a dictionnary of oligos and the characters with which to replace them"
    oligs = {
        i.replace('!', '').lower()
        for i in oligos if i.lower() not in ('$', '0', 'doublestrand', 'singlestrand')
    }

    lst = {i: ''.join(chr(0x1d58d+ord(j)) for j in i) for i in oligs}

    oligs = {Translator.reversecomplement(i) for i in oligs}-oligs
    lst.update({i: ''.join(chr(0x1d5f5+ord(j)) for j in i) for i in oligs})
    return lst

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

class NonLinearities(Translator):
    """
    Computes the non-linearities created by oligos binding to a hairpin
    """
    sequence     = None
    singlestrand = .55  # nm
    doublestrand = .34  # nm
    orientation  = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def difference(self, oligos: Union[str, Iterable[str]]):
        """
        returns the difference to the a single strand in nm
        """
        size  = np.zeros(len(self.sequence), dtype = 'f4') # type: ignore
        diff  = self.doublestrand - self.singlestrand
        allo  = (oligos,) if isinstance(oligos, str) else oligos
        for olig in cast(Iterable[str], allo):
            pks  = self.peaks(cast(str, self.sequence), olig)
            good = pks['position']
            if self.orientation is not None:
                good = good[pks['orientation'] == self.orientation]
            for i in good:
                size[i:] += diff
        return size

    def nonlinearities(self, oligos: Union[str, Iterable[str]]):
        """
        returns the non-linearities created by the oligos in nm
        """
        size   = self.difference(oligos)
        single = np.arange(len(size), dtype = 'f4') * self.singlestrand
        double = size+single
        return double - np.polyval(np.polyfit(single, double, 1), single)

class LNAHairpin:
    """The theoretical sequence: full, target, references"""
    full:       str       = ""
    target:     str       = ""
    references: List[str] = []
    @initdefaults(frozenset(locals()),
                  path = lambda self, val: self.setfrompath(val))
    def __init__(self, **_):
        pass

    def setfrompath(self, file_sequence: Union[str, Path],
                    full:   str = 'full',
                    target: str = 'target',
                    references: Union[Iterable[str], str] = None):
        """file_sequence is the path of the fasta file
         format of the file:
            > full
            (...)cccatATTCGTATcGTcccat(...)
            > oligo
            cccat,tgtca
            > target
            TCGTAT
        """
        text = dict(read(file_sequence))

        self.full       = text.pop(full)
        self.target     = self.full if target is None else text.pop(target)

        if isinstance(references, str):
            references = [i.strip() for i in references.split(',')]
        itr = (text.values() if not references else (text[i] for i in references))
        self.references = sum((i.split(',') for i in itr), [])

class Strand(Enum):
    """
    Which strand we sit on
    """
    positive = True
    negative = False

    @classmethod
    def _missing_(cls, value):
        return getattr(cls, value)
