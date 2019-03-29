#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All sequences-related stuff"
import pytest
from numpy.testing         import assert_allclose
from sequences             import peaks, overlap, splitoligos, Translator
from sequences.meltingtime import OldStatesTransitions, StatesTransitions

def test_peaks():
    "tests peaks"
    seq = "atcgATATATgtcgCCCaaGGG"
    res = peaks(seq, ('+ATAT', 'CCC'))
    assert len(res) == 4
    assert all(a == b for a, b in zip(res['position'],    [8, 10, 17, 22]))
    assert all(a == b for a, b in zip(res['orientation'], [True]*3+[False]))

    res = peaks(seq, ('-ATAT', 'CCC'))
    assert len(res) == 4
    assert all(a == b for a, b in zip(res['position'],    [8, 10, 17, 22]))
    assert all(a == b for a, b in zip(res['orientation'], [False]*2+[True, False]))

    res = peaks(seq, ('ATAT', 'CCC'))
    assert len(res) == 4
    assert all(a == b for a, b in zip(res['position'],    [8, 10, 17, 22]))
    assert all(a == b for a, b in zip(res['orientation'], [True]*3+[False]))

    res = peaks(seq, ('ATAT', '+CCC'))
    assert len(res) == 3
    assert all(a == b for a, b in zip(res['position'],    [8, 10, 17]))
    assert all(a == b for a, b in zip(res['orientation'], [True]*3))

    res = peaks(seq, ('ATAT', '-CCC'))
    assert len(res) == 3
    assert all(a == b for a, b in zip(res['position'],    [8, 10, 22]))
    assert all(a == b for a, b in zip(res['orientation'], [True]*2+[False]))

    res = peaks(seq, 'ATAT')
    assert len(res) == 2
    assert all(a == b for a, b in zip(res['position'],    [8, 10]))
    assert all(a == b for a, b in zip(res['orientation'], [True]*2))

    res = peaks(seq, "$")
    assert len(res) == 1
    assert all(a == b for a, b in zip(res['position'],    [len(seq)]))
    assert all(a == b for a, b in zip(res['orientation'], [True]))

    res = peaks(seq, ('A!TAT', '!CCC'))
    assert len(res) == 6
    assert all(a == b for a, b in zip(res['position'],    [6, 7, 8, 9, 15, 22]))
    assert all(a == b for a, b in zip(res['orientation'], [True,False,True,False,True,False]))

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

def test_rv():
    "testing reverse complements"
    assert Translator.reversecomplement("atgcws") == "swgcat"
    assert Translator.reversecomplement("ATGCws") == "swGCAT"

def test_splits():
    "testing oligo splitting"
    assert splitoligos('AtG') == ['atg']
    assert splitoligos(':AtG;') == ['atg']
    assert splitoligos('AtG;ttt') == ['atg', 'ttt']
    assert splitoligos('AtG;ttt;') == ['atg', 'ttt']
    assert splitoligos('AtG;ttwt;') == ['atg', 'ttwt']
    assert splitoligos('-AtG;ttwt;') == ['-atg', 'ttwt']
    assert splitoligos('+AtG;ttwt;') == ['+atg', 'ttwt']
    assert splitoligos('AtG;-ttwt;') == ['-ttwt', 'atg']
    assert splitoligos('AtG;+ttwt;') == ['+ttwt', 'atg']
    assert splitoligos('+AtG') == ['+atg']
    assert splitoligos(':-AtG;') == ['-atg']
    assert splitoligos('-AtG') == ['-atg']
    assert splitoligos(':+AtG;') == ['+atg']

_MODES = [
    ('o', 'CTAG',  'GATC',   (2.955491253e-05, 33835.3225, 0.72671001, -3.0670222, -57.58380)),
    ('o', 'GATC',  'CTAG',   (2.031866819e-05, 49215.8241, 0.58278606, -2.4716049, -62.03634)),
    ('o', 'TATA',  'ATAT',   (6.126166266e-06, 163234.224, 0.28811599, -0.5681770, -88.47045)),
    ('o', 'CCCCC', 'GGGGG',  (0.008945123,     111.792752, 1.43969394, -9.4632943, -16.72818)),
    ('o', 'GGGGG', 'CCCCC',  (0.008945123,     111.792752, 1.43969394, -9.4632943, -16.72818)),
    ('o', 'GGGGC', 'CCCCC',  (0.000535680,     1866.78433, 0.24657030, -4.8834298, -45.86585)),
    ('o', 'GGGCG', 'CCCCC',  (3.308497796e-05, 30225.1977, 0.02468661,  0.2024148, -107.1183)),
    ('o', 'GGCGG', 'CCCCC',  (2.479741968e-05, 40326.7764, 0.03293713,  0.2024148, -107.1183)),
    ('o', 'GCGGG', 'CCCCC',  (3.104584692e-05, 32210.4274, 0.02630805,  0.2024148, -107.1183)),
    ('o', 'CGGGG', 'CCCCC',  (0.001460713,     684.596864, 0.93851525, -7.2232242, -31.68077)),
    ('f',  "CTAG",  "GATC",  (6.785250875e-05, 14737.8485, 0.37559711, -3.2380981, -57.58380)),
    ('f',  "GATC",  "CTAG",  (5.061968773e-05, 19755.1593, 0.27757623, -2.6426809, -62.03634)),
    ('f',  "TATA",  "ATAT",  (1.641822285e-05, 60907.9319, 0.12756376, -0.7392529, -88.47045)),
    ('f',  "CCCCC", "GGGGG", (0.001813628,     551.380913, 8.92013390, -9.6913956, -16.72818)),
    ('f',  "GGGGG", "CCCCC", (0.001813628,     551.380913, 8.92013390, -9.6913956, -16.72818)),
    ('f',  "GGGGC", "CCCCC", (0.0004454839728, 2244.74966, 0.37245830, -5.1115310, -45.86585)),
    ('f',  "GGGCG", "CCCCC", (6.865708639e-05, 14565.1389, 0.01494411, -0.0256863, -107.1183)),
    ('f',  "GGCGG", "CCCCC", (6.900976316e-05, 14490.7032, 0.01486773, -0.0256863, -107.1183)),
    ('f',  "GCGGG", "CCCCC", (6.353794618e-05, 15738.6264, 0.01614813, -0.0256863, -107.1183)),
    ('f',  "CGGGG", "CCCCC", (0.0004952853667, 2019.03804, 3.47707491, -7.4513254, -31.68077))
]

@pytest.mark.parametrize("mode,seq,oligo", [i[:3] for i in _MODES])
def test_oldmt(mode, seq, oligo):
    "test melting times"
    truth = next(i[-1] for i in _MODES if i[:-1] == (mode, seq, oligo))
    cnf = OldStatesTransitions()
    cnf.setmode('oligo' if mode == 'o' else 'fork')

    out   = cnf(seq, oligo)
    assert_allclose(out, list(truth), rtol=5e-4, atol=5e-8)

    if mode == 'o':
        out   = cnf(oligo[::-1], seq[::-1])
        assert_allclose(out, list(truth), rtol=5e-4, atol=5e-8)

_MODES2 = [
    *_MODES[:10],
    # hairpin computations differ significantly: the old version strangely
    # allows the hairpin to hybridize to the 1st base hybridized by the oligo
    ('f',  "CTAG",  "GATC",  (0.00010436374,     9581.8719752, 0.244195, -3.2380981, -57.58380)),
    ('f',  "GATC",  "CTAG",  (8.30453568363e-05, 12041.612416, 0.169194, -2.6426809, -62.03634)),
    ('f',  "TATA",  "ATAT",  (4.72008782560e-05, 21186.046466, 0.044371, -0.7392529, -88.47045)),
    ('f',  "CCCCC", "GGGGG", (0.00754787433,     132.48763229, 2.143359, -9.6913956, -16.72818)),
    ('f',  "GGGGG", "CCCCC", (0.00754787433,     132.48763229, 2.143359, -9.6913956, -16.72818)),
    ('f',  "GGGGC", "CCCCC", (0.00121853960,     820.65449423, 0.136166, -5.1115310, -45.86585)),
    ('f',  "GGGCG", "CCCCC", (0.00013198550,     7576.5894546, 0.007773, -0.0256863, -107.1183)),
    ('f',  "GGCGG", "CCCCC", (8.49332498433e-05, 11773.951919, 0.012080, -0.0256863, -107.1183)),
    ('f',  "GCGGG", "CCCCC", (7.56045894770e-05, 13226.710268, 0.013570, -0.0256863, -107.1183)),
    ('f',  "CGGGG", "CCCCC", (0.00111728387,     895.02768558, 1.541366, -7.4513254, -31.68077)),
    ('f',  "GGGGG", "CCCCC", (0.00754787433,     132.48763229, 2.143359, -9.6913956, -16.72818)),
    ('f',  "CCCCC", "GGGGG", (0.00754787433,     132.48763229, 2.143359, -9.6913956, -16.72818)),
    ('f',  "CCCCC", "GGGGC", (2.932971e-03,      3.409512e+02, 0.587167, -7.451325,  -31.68077)),
    ('f',  "CCCCC", "GGGCG", (1.261359e-04,      7.927959e+03, 0.008134, -0.0256863, -107.1184)),
    ('f',  "CCCCC", "GGCGG", (8.541771e-05,      1.170717e+04, 0.012011, -0.0256863, -107.1184)),
    ('f',  "CCCCC", "GCGGG", (7.846563e-05,      1.274443e+04, 0.013076, -0.0256863, -107.1184)),
    ('f',  "CCCCC", "CGGGG", (4.025846e-04,      2.483950e+03, 0.412147, -5.111531,  -45.86586))
]

@pytest.mark.parametrize("mode,seq,oligo", [i[:3] for i in _MODES2])
def test_mt(mode, seq, oligo):
    "test melting times"
    truth = next(i[-1] for i in _MODES2 if i[:-1] == (mode, seq, oligo))

    cnf   = StatesTransitions(seq, oligo, force = 0 if mode == "o" else 8.5)
    out   = cnf.statistics(*(('hpin',) if mode == "o" else ()), ini = 'hybridized')
    assert_allclose(out, list(truth), rtol=5e-4, atol=5e-8)

    if mode != 'f':
        cnf   = StatesTransitions(oligo[::-1], seq[::-1], force = 0 if mode == "o" else 8.5)
        out   = cnf.statistics(*(('hpin',) if mode == "o" else ()), ini = 'hybridized')
        assert_allclose(out, list(truth), rtol=5e-4, atol=5e-8)

if __name__ == '__main__':
    for i in _MODES[9:]:
        test_mt(*i[:-1])
