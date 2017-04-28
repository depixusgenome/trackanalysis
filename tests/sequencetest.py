#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All sequences-related stuff"
from sequences import peaks, overlap

def test_peaks():
    "tests peaks"
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

    seq = "a"*5+"t"+"a*5"
    res = tuple(tuple(i) for i in peaks(seq, 'a!taa')) == ((5, True),)
    res = tuple(tuple(i) for i in peaks(seq, 't!att')) == ((6, False),)
    res = tuple(tuple(i) for i in peaks(seq, 't!a!tt')) == ((6, False), (7, False))
    res = tuple(tuple(i) for i in peaks(seq, 'a!t!aa')) == ((5, True), (6, True))

def test_overlap():
    "tests overlaps"
    assert  not overlap('ATAT', '')
    assert  overlap('ATAT', 'ATAT')
    assert  overlap('ATAT', 'CATA')
    assert  overlap('ATAT', 'CCAT')
    assert  overlap('ATAT', 'CCCA')
    assert  overlap('ATAT', 'ATAT', minoverlap = 4)
    assert  overlap('ATAT', 'CATA', minoverlap = 3)
    assert  overlap('ATAT', 'CCAT', minoverlap = 2)
    assert  overlap('ATAT', 'CCCA', minoverlap = 1)
    assert  not overlap('ATAT', 'ATAT', minoverlap = 5)
    assert  not overlap('ATAT', 'CATA', minoverlap = 4)
    assert  not overlap('ATAT', 'CCAT', minoverlap = 3)
    assert  not overlap('ATAT', 'CCCA', minoverlap = 2)

    assert  not overlap('', 'ATAT')
    assert  overlap('ATAT', 'ATAT')
    assert  overlap('CATA', 'ATAT')
    assert  overlap('CCAT', 'ATAT')
    assert  overlap('CCCA', 'ATAT')
    assert  overlap('ATAT', 'ATAT', minoverlap = 4)
    assert  overlap('CATA', 'ATAT', minoverlap = 3)
    assert  overlap('CCAT', 'ATAT', minoverlap = 2)
    assert  overlap('CCCA', 'ATAT', minoverlap = 1)
    assert  not overlap('ATAT', 'ATAT', minoverlap = 5)
    assert  not overlap('CATA', 'ATAT', minoverlap = 4)
    assert  not overlap('CCAT', 'ATAT', minoverlap = 3)
    assert  not overlap('CCCA', 'ATAT', minoverlap = 2)

if __name__ == '__main__':
    test_peaks()
