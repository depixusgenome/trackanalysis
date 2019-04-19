#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
import numpy as np
from   numpy.testing            import assert_equal, assert_allclose

from   tests.testutils          import integrationmark
from   tests.testingcore        import path as utpath

from   cleaning.processor       import (DataCleaningTask, DataCleaningException,
                                        DataCleaningProcessor, BeadSubtractionTask,
                                        BeadSubtractionProcessor, ClippingTask)
import cleaning.datacleaning    as     _datacleaning
from   cleaning.datacleaning    import (DataCleaning, LocalNaNPopulation,
                                        DerivateIslands)
from   cleaning.beadsubtraction import (SubtractAverageSignal, SubtractMedianSignal,
                                        FixedBeadDetection)
import cleaning._core           as     cleaningcore # pylint:disable=no-name-in-module,import-error
from   data                       import Beads, Track
from   taskcontrol.taskcontrol    import create
from   taskmodel.track            import TrackReaderTask
from   simulator                  import randtrack, setseed
from   simulator.bindings         import Experiment

def test_datacleaning():
    "test data cleaning"
    bead = np.concatenate([np.random.normal(.1, 3e-3, 200),
                           np.random.normal(.1, 3e-5, 200),
                           np.random.normal(.1, 3e-2, 200)]).astype('f4')
    out = _datacleaning.HFSigmaRule().hfsigma(bead, [0,200, 400], [200, 400, 600])
    assert out.name == "hfsigma"
    assert list(out.min) == [1]
    assert list(out.max) == [2]

    bead = np.concatenate([np.random.normal(.1, 3e-3,  100), np.random.normal(1.1, 3e-3, 100),
                           np.random.normal(.5, 3e-3,  100), np.random.normal(.6, 3e-3,  100),
                           np.random.normal(-2., 3e-3, 100), np.random.normal(.6, 3e-3,  100)]
                         ).astype('f4')
    out = _datacleaning.ExtentRule().extent(bead, [0,200, 400], [200, 400, 600])
    assert out.name == "extent"
    assert list(out.min) == [1]
    assert list(out.max) == [2]

    bead = np.ones(600, dtype = 'f4')
    bead[200:400:2] = np.NaN
    bead[400:600:6] = np.NaN
    out = _datacleaning.PopulationRule().population(bead, [0,200, 400], [200, 400, 600])
    assert out.name == "population"
    assert list(out.min) == [1]
    assert list(out.max) == []

    bead = np.random.normal(.1, 3e-3,  600).astype('f4')
    bead[50:100]  += 1
    bead[250:300] += 1
    bead[330:340] += 1
    bead[350:360] += 1
    bead[370:380] += 1
    bead[450:500] += 1
    bead[570:580] += .1
    out = _datacleaning.PingPongRule().pingpong(bead, [0,200, 400], [200, 400, 600])
    assert out.name == "pingpong"
    assert list(out.min) == []
    assert list(out.max) == [1]


    bead = np.random.normal(.1, 3e-3, 1000).astype('f4')
    for i in range(70,1000,100):
        bead[i:i+10] += .02
    out = _datacleaning.SaturationRule().saturation(bead,
                                                    list(range(0,1000,100)),
                                                    list(range(30,1000,100)),
                                                    list(range(50,1000,100)),
                                                    list(range(90,1000,100)))
    assert out.name == "saturation"
    assert list(out.min) == []
    assert list(out.max) == []

    for i in range(80,800,100):
        bead[i:i+10] += .02
    out = _datacleaning.SaturationRule().saturation(bead,
                                                    list(range(0,1000,100)),
                                                    list(range(30,1000,100)),
                                                    list(range(50,1000,100)),
                                                    list(range(90,1000,100)))
    assert out.name == "saturation"
    assert list(out.min) == []
    assert list(out.max) == list(range(10))

def test_constantvalues():
    "test constant values"
    setseed(0)
    bead = np.asarray(np.random.normal(.1, 3e-3, 50), dtype = 'f4')

    bead[:3]    = 100.
    bead[10:13] = 100.
    bead[20:30] = 100.
    bead[40:42] = 100.
    bead[-3:]   = 100.

    fin                  =  np.abs(bead-100.) < 1e-5
    fin[[0,10,20,40,41,-3]] = False

    # pylint: disable=c-extension-no-member
    cleaningcore.constant(DataCleaning(), bead)

    assert_equal(np.isnan(bead), fin)

    bead[:3]    = 100.
    bead[10:13] = 100.
    bead[20:30] = 100.
    bead[40:42] = 100.
    bead[-3:]   = 100.

    cleaningcore.constant(DataCleaning(mindeltarange=5), bead)
    fin[:] = False
    fin[21:30] = True
    assert_equal(np.isnan(bead), fin)

def test_cleaning_localpop():
    "test cleaning"
    setseed(0)
    cycs = np.ones(100, dtype = 'f4')
    cycs[[7, 10, 19, 21]] = np.NaN
    LocalNaNPopulation(window = 1, ratio = 50).apply(cycs)
    assert set(np.nonzero(np.isnan(cycs))[0]) == {7, 10, 19, 20, 21}

    cycs = np.ones(100, dtype = 'f4')
    cycs[[7, 10, 19, 21, 30, 48, 49, 51,52]] = np.NaN
    LocalNaNPopulation(window = 3, ratio = 50).apply(cycs)
    assert set(np.nonzero(np.isnan(cycs))[0]) == {7, 10, 19, 21, 30, 48, 49, 50, 51, 52}

    cycs = np.ones(100, dtype = 'f4')
    cycs[5:15]  = np.NaN
    cycs[20:35] = np.NaN
    cycs[15:20:2] = 2
    cycs[55:65] = np.NaN
    cycs[70:85] = np.NaN

    DerivateIslands().apply(cycs)
    assert np.all(np.isnan(cycs[5:35]))
    assert np.all(np.isfinite(cycs[65:70]))

    arr = np.array([-0.79690832, -0.79579473, -0.79837704, -0.79940188, -0.79769713,
                    -0.79858971, -0.8066749 , -0.79106545, -0.77895606, -0.7706582 ,
                    -0.77465558, -0.77435076, -0.77996087, -0.78103262, -0.77927762,
                    -0.78047663, -0.78048003, -0.77914697, -0.77894264, -0.77992404,
                    -0.77949697, -0.77788597, -0.78004122, -0.77818239, -0.7810092 ,
                    -0.7793898 , -0.77930272, -0.77732331, -0.77962595, -0.77978671,
                    -0.7788288 , -0.77856421, -0.77925581, -0.77864963, -0.77837831,
                    -0.77977329, -0.77696157, -0.77685273, -0.77776206, -0.77795631,
                    -0.77678406, -0.7785123 , -0.7777704 , -0.77726465, -0.77831131,
                    -0.77777374, -0.77750915, -0.77546442, -0.77564865, -0.77878022,
                    -0.77860773, -0.77585459, -0.7786563 , -0.77707374, -0.77574074,
                    -0.7501353 ,  0.26812187,  0.31527671,  0.3164272 ,  0.31748557,
                    0.3185356 ,  0.31630158,  0.316459  ,  0.31393698,  0.31447122,
                    0.31282166,  0.31457502,  0.30616325,  0.30708095,  0.30723169,
                    0.30934343,  0.30663216,  0.30794007,  0.30851448,  0.30675775,
                    0.30759844,  0.30739748,  0.30455393,  0.30876565,  0.30855298,
                    0.30791494,  0.30829844,  0.30685487,  0.30877739,  0.30876902,
                    0.30888289,  0.30899006,  0.31002501,  0.30741757,  0.30926639,
                    0.30778432,  0.30897498,  0.30738074,  0.30640441,  0.30680129,
                    0.3068532 ,  0.30666229,  0.30953434,  0.30724841,  0.30636254,
                    0.30695704,  0.30869702,  0.30749628,  0.30847931,  0.30836877,
                    0.30936185,  0.30915922,  0.30615821,  0.30661038,  0.30747786,
                    0.30648646,  0.30842069,  0.30828336,  0.30881089,  0.30803385,
                    0.30877906,  0.30902523,  0.30809915,  0.30503118,  0.30696708,
                    0.30588025,  0.30763695,  0.30709437,  0.30828002,  0.30728191,
                    0.30842906,  0.30764866,  0.31009701,  0.30849269,  0.30674604,
                    0.30868194,  0.30879247,  0.30492568,  0.30191466,  0.30321085,
                    0.29948139,  0.29817852,  0.29433686,  0.29170263,  0.28980693,
                    0.28499398,  0.28016594,  0.27730063,  0.27050322,  0.26700318,
                    0.26460844,  0.26067132,  0.25439641,  0.2523098 ,  0.25179902,
                    0.25031194,  0.24609515,  0.24244106,  0.23897454,  0.23580945,
                    0.23317689,  0.2289082 ,  0.22581512,  0.2192689 ,  0.2144593 ,
                    0.20362765,  0.2033145 ,  0.20206185,  0.19907427,  0.19446731,
                    0.19199552,  0.19191514,  0.18714739,  0.18154569,  0.18048061,
                    0.17692365,  0.17281573,  0.16971929,  0.16367045,  0.1537046 ,
                    -0.45437163, -0.63843936, -0.64093626, -0.64427382, -0.64571238,
                    -0.64453173, -0.64179367, -0.64197117, -0.64262766, -0.64190757,
                    -0.64146209, -0.64270133, -0.64420688, -0.64482147, -0.64152074,
                    -0.64419848, -0.64550471, -0.64290231, -0.64345497, -0.6427114 ,
                    -0.64355874, -0.64473605, -0.64359224, -0.64451164, -0.64280516,
                    -0.64286715, -0.64420521, -0.64467239, -0.64205325, -0.64507264,
                    -0.64334607, -0.64301956, -0.64214367, -0.64428222, -0.64446813,
                    -0.64295423, -0.64246356, -0.64155757, -0.64224917, -0.6427784 ,
                    -0.64406115, -0.6434918 , -0.64333439, -0.64360899, -0.64481306,
                    -0.64270473, -0.64403272, -0.6430999 , -0.67473745, -0.79247218,
                    -0.79145402, -0.79141885, -0.79067695, -0.79145902, -0.79176044,
                    -0.79329109, -0.79151428, -0.79152936, -0.79239684, -0.79197484,
                    -0.7905966 , -0.79071212, -0.79121953, -0.79056644, -0.79232484,
                    -0.79238343, -0.79261285, -0.79008579, -0.79184586, -0.79023319,
                    -0.78982788, -0.79302484, -0.79079586, -0.78996688, -0.79096162,
                    -0.79191118, -0.79306668, -0.79061329, -0.78972745, -0.79073387,
                    -0.79207695, -0.7926966 , -0.79133177, -0.79154778, -0.793827  ,
                    -0.79391074, -0.79265475, -0.79345518, -0.79263628, -0.79296786,
                    -0.79080927, -0.79352385, -0.79074562, -0.7912547 , -0.7908411 ,
                    -0.79192293, -0.7916131 , -0.79367626, -0.78983796, -0.79154611,
                    -0.79072553, -0.79180068, -0.79199159, -0.79205853, -0.79060829,
                    -0.79282385, -0.79335976, -0.79343343, -0.79355735, -0.79427075,
                    -0.79190278, -0.79158294, -0.79227459, -0.79322577, -0.79118103,
                    -0.79201335, -0.79186261, -0.79087627, -0.79112077, -0.79175878,
                    -0.79072052, -0.78851998, -0.79032028, -0.79279709, -0.79078078,
                    -0.7904157 , -0.79099345, -0.79105544, -0.7902717 , -0.79197145,
                    -0.79151094, -0.79026163, -0.7891463 , -0.78936237, -0.7896772 ,
                    -0.78910947, -0.78851163, -0.79060829, -0.78855687, -0.79092646,
                    -0.78965545, -0.79054469, -0.7907607 , -0.78946286, -0.78959513,
                    -0.78932047, -0.79012263, -0.79010421, -0.7891162 , -0.78954321,
                    -0.78704965, -0.78979272, -0.7894913 , -0.78906429, -0.78868747,
                    -0.78714007, -0.78972912, -0.78958338, -0.79014444, -0.79014778,
                    -0.78971237, -0.78905755, -0.78892362, -0.79149586, -0.79061329,
                    -0.78874779, -0.78718197, -0.7908076 , -0.78937405, -0.78932554,
                    -0.79052454, -0.79170352, -0.79542291, -0.79588681, -0.79687822,
                    -0.79660356, -0.79465091, -0.79611123, -0.79817438, -0.79855955,
                    -0.79951578, -0.7998842 , -0.79847747, -0.79986912, -0.80512083,
                    -0.80317992, -0.80380118, -0.80255026, -0.80680722, -0.80627131,
                    -0.80948836, -0.81511182, -0.82188576, -0.82000852, -0.81865537,
                    -0.82027143, -0.82083744, -0.81858337, -0.82017928, -0.82363582,
                    -0.82515973, -0.82696497, -0.82988393, -0.83153176, -0.83078992,
                    -0.83358324, -0.83392823, -0.83427656, -0.8343519 , -0.83615714,
                    -0.84034044, -0.84082109, -0.84304667, -0.84583163, -0.84543139,
                    -0.84543139, -0.84466773, -0.84578139, -0.84807903, -0.84571606,
                    -0.84598237, -0.84798521, -0.84601921, -0.84720147,  0.23271804,
                    -0.29640171, -0.67998415,  1.15229964,  1.01592267,  1.02059829,
                    0.89711452,  1.12195837,  0.89550346,  1.13562679,  0.89703578,
                    1.11898744, -0.78947121,  1.02059829, -0.78050178, -0.9886108 ,
                    3.06132269, -0.9549017 ,  0.89506471, -1.1455977 , -0.83611697,
                    0.32207078, -0.50481719, -0.9549017 ,  1.68186653,  0.22797877,
                    -0.88662952,  0.2260077 , -0.31466547, -0.9549017 ,  1.68827713,
                    0.14793709, -0.88476229,  0.21960719, -0.13675544, -0.9549017 ,
                    1.69935489,  0.1324767 , -0.88176131,  0.22719671, -0.29949814,
                    -0.9549017 ,  1.70055234,  0.11482755, -0.88263547,  0.21665478,
                    -0.32800406,  2.60654593,  1.02985919, -0.29640171, -1.1507473 ,
                    -0.83265376,  0.3110432 , -0.35766214,  0.77524   ,  1.43363285,
                    0.15359741, -0.87574089,  0.17985931,  1.71257961,  0.141066  ,
                    -0.87663352,  0.1784593 ,  1.69881403,  0.15550317, -0.8627674 ,
                    1.15399945, -2.26308632, -0.9549017 ,  1.91441035, -0.9549017 ,
                    1.91015851, -0.9549017 ,  1.90890419, -0.9549017 ,  1.91288984,
                    -0.3165997 ,  1.91493285, -0.34299389,  1.91323817, -0.33744073,
                    1.90628839, -0.30488551,  1.90371776, -0.9549017 ,  1.91172767,
                    -0.9549017 ,  1.90611923, -0.43080762,  1.91227853, -0.9549017 ,
                    1.91879797,  2.92314053, -0.9549017 , -0.9549017 ,  1.91471016,
                    2.91558456, -0.9549017 , -0.9549017 ,  1.91381252,  2.91820192,
                    -0.9549017 , -0.9549017 ,  1.91015172,  2.91662264, -0.9549017 ,
                    -0.9549017 ,  1.91185653,  2.92125154, -0.9549017 , -0.9549017 ,
                    1.90828621,  2.92419887, -1.84687841, -0.9549017 ,  1.91498983,
                    2.92668748, -0.9549017 , -0.9549017 ,  1.9069699 ,  2.92263317,
                    -1.86609507, -0.9549017 ,  1.90924919,  2.91151333, -0.9549017 ,
                    -0.9549017 ,  1.91351783,  2.90387702, -1.91809964, -0.9549017 ,
                    1.90500391,  2.90233135, -1.9161303 , -0.45364484,  1.90994585,
                    2.9040277 , -1.933622  , -0.9549017 ,  1.90476608,  2.91356492,
                    -0.9549017 , -0.9549017 ,  1.90671206,  2.90125775, -0.9549017 ,
                    -0.4734208 ,  1.90962756,  2.90397573, -1.95691645, -0.9549017 ,
                    1.90673208,  2.91650891, -0.9549017 , -0.9549017 ,  1.90102661,
                    2.90890598, -1.93429184, -0.9549017 ,  1.90349507,  2.90565872,
                    -1.91835427, -0.9549017 ,  1.90517306,  2.90558672, -0.9549017 ,
                    -0.9549017 ,  1.88734305, -0.82788771,  0.96333027, -0.81194502,
                    2.46210027, -0.31918201,  2.47056746, -0.30896661,  2.46491718,
                    1.01052022, -0.9549017 ,  0.47256505,  1.65335894,  0.62549931,
                    -0.78940755,  0.47687393,  1.6197269 ,  0.68371022, -0.79325759,
                    0.45093191, -0.64100158, -0.29640171, -0.17973706,  1.12224638,
                    -0.9549017 , -0.29640171, -0.16009842,  1.08538055, -0.9549017 ,
                    -0.29640171,  2.60099936,  0.5088464 , -0.9549017 , -0.29640171,
                    -0.1922936 ,  0.56249726, -0.9549017 , -0.29640171, -0.15822281,
                    0.54534709, -0.9549017 , -0.29640171,  3.31478143,  1.09355795,
                    -0.9549017 , -0.29640171, -0.16294031,  1.04149961, -0.9549017 ,
                    -0.29640171,  3.2855587 ,  1.08268607, -0.9549017 , -0.27071589,
                    3.2445817 ,  1.02340841, -0.9549017 ,  1.67909837, -0.8317076 ,
                    -0.83142459, -0.83329183, -0.83211458, -0.83299541, -0.83303559,
                    -0.83331698, -0.83372223, -0.83293349, -0.83298367, -0.83324158,
                    -0.83297032, -0.82993245, -0.83008653, -0.82989901, -0.83223683,
                    -0.82922912, -0.8308351 , -0.83033943, -0.82887411, -0.83005977,
                    -0.83031094, -0.83213967, -0.83699787, -0.8560403 , -0.85914177,
                    -0.86683679, -0.86726886, -0.87130809, -0.86744469, -0.86922818,
                    -0.86806601, -0.86630088, -0.86924326, -0.8674916 , -0.86818486,
                    -0.87211698, -0.86949277, -0.87274832, -0.87601554, -0.87541103,
                    -0.8725574 , -0.87290406, -0.87549305, -0.87504256, -0.87342489,
                    -0.87300116, -0.87083751, -0.88013518, -0.87838852, -0.8822754 ,
                    -0.87751102, -0.87583303, -0.87965626, -0.87988067, -0.88071299,
                    -0.88141632, -0.88385463, -0.88159049, -0.8829084 , -0.88501513,
                    -0.88616896, -0.88570678, -0.88548237, -0.88933742, -0.88768119,
                    -0.88660103, -0.88588595, -0.88925868, -0.88837284, -0.8890996 ,
                    -0.89062858, -0.88894892, -0.88983309, -0.88590437, -0.89197832,
                    -0.88852859, -0.889036  , -0.88628954, -0.88630629, -0.88669652,
                    -0.88171941, -0.88119024, -0.87675744, -0.85422164, -0.8367902 ,
                    -0.84964311, -0.85187709, -0.84820628, -0.85193574, -0.84651989,
                    -0.84993786, -0.84792829, -0.84808236, -0.84649312, -0.84962469,
                    -0.84933168, -0.84688663, -0.84930319, -0.85057926, -0.84624189,
                    -0.85059267, -0.84749454, -0.84904027, -0.84867352, -0.8457278 ,
                    -0.84680128, -0.85208476, -0.8472718 , -0.84709263, -0.84670413,
                    -0.84913737, -0.85468549, -0.84779769, -0.84975702, -0.85384989,
                    -0.84626538, -0.84746945, -0.85406756, -0.84740245, -0.84679455,
                    -0.8487556 , -0.85013884, -0.84805053, -0.84800196, -0.85113859,
                    -0.85277474, -0.8499831 , -0.85259891], dtype='f4')

    DataCleaningTask().aberrant(arr)
    assert np.all(np.isnan(arr[401:624]))

def test_subtract(monkeypatch):
    "tests subtractions"
    import cleaning.processor._beadsubtraction as C
    monkeypatch.setattr(C, '_cleaningcst', lambda *x: None)

    agg = SubtractAverageSignal.apply
    _   = dict(dtype = 'f4')
    assert_allclose(agg([np.arange(5, **_)]),             np.arange(5, **_))
    assert_allclose(agg([np.arange(5, **_)]*5),           np.arange(5, **_))
    assert_allclose(agg([np.arange(5, **_), np.ones(5, **_)]), np.arange(5, **_)*.5+.5)
    assert_allclose(agg([np.arange(6, **_), np.ones(5, **_)]), list(np.arange(5, **_)*.5+.5)+[5])

    tmp = Beads(data = {0: np.arange(5, **_), 1: np.ones(5, **_),
                        2: np.zeros(5, **_),  3: np.arange(5, **_)*1.})
    cache: dict = {}
    frame = BeadSubtractionProcessor.apply(tmp, cache,
                                           beads = [0, 1],
                                           agg   = SubtractAverageSignal())
    assert set(frame.keys()) == {2, 3}
    assert_allclose(frame[2], -.5*np.arange(5, **_)-.5)
    assert_allclose(cache[None],  .5*np.arange(5, **_)+.5)

    ca0 = cache[None]
    res = frame[3]
    assert res is not frame.data[3] # pylint: disable=unsubscriptable-object
    assert ca0 is cache[None]

def test_subtract_med():
    "tests subtractions"
    _    = dict(dtype = 'f4')
    agg  = lambda x: SubtractMedianSignal.apply([i.astype('f4') for i in x], (0,5))
    assert_allclose(agg([np.arange(5, **_)]*5),           np.arange(5, **_))
    assert_allclose(agg([np.arange(5, **_), np.ones(5, **_)]), np.arange(5, **_)*.5+.5)
    assert_allclose(agg([np.arange(5, **_)]+[np.ones(5, **_)]*2), np.ones(5, **_))
    assert_allclose(agg([np.arange(6, **_), np.ones(5, **_)]), list(np.arange(5, **_)*.5+.5)+[4.5])

    tsk             = BeadSubtractionTask(beads = [1,2,3,4])
    tsk.agg.average = True
    cache = {} # type: ignore
    frame = BeadSubtractionProcessor.apply(Track(**Experiment().track(1, 5)).beads,
                                           cache = cache, **tsk.config())
    out   = frame[0]
    assert out is not None

def test_processor():
    "test processor"
    # pylint: disable=expression-not-assigned
    cache = {} # type: ignore
    trk   = randtrack().beads
    DataCleaningProcessor.apply(trk, cache = cache, maxsaturation = 100)[0]
    assert list(cache) == [0]
    tmp = cache[0]
    DataCleaningProcessor.apply(trk, cache = cache, maxsaturation = 100)[0]
    assert tmp is cache[0]

def test_processor2():
    "test processor"
    proc  = create(utpath("big_all"), DataCleaningTask())
    _     = next(iter(proc.run()))[0]
    cache = proc.data[1].cache()
    assert list(cache) == [0]

def test_message_creation():
    "test message creation"
    proc  = create(TrackReaderTask(path = utpath("big_legacy")),
                   DataCleaningTask())
    data  = next(iter(proc.run()))
    try:
        data[5]
    except DataCleaningException:
        pass
    else:
        assert False

@integrationmark
def test_cleaningview(bokehaction):
    "test the view"
    server = bokehaction.start('cleaning.view.CleaningView', 'taskapp.toolbar')
    server.load('big_legacy')

    assert 'config.tasks' not in server.savedconfig

    assert server.task(DataCleaningTask).maxhfsigma != 0.002
    server.change('Cleaning:Filter', 'maxhfsigma', 0.002)
    server.wait()
    assert server.widget['Cleaning:Filter'].maxhfsigma == 0.002
    assert server.task(DataCleaningTask).maxhfsigma == 0.002

    cnf = server.savedconfig['config.tasks']['picotwist']['datacleaning']
    assert cnf.maxhfsigma == 0.002

    server.change('Cleaning:Filter', 'subtracted', "11")
    server.wait()

    server.change('Cleaning:Filter', 'subtracted', "11,30")

def test_fixedbeadsorting():
    "test fixed bead detection"
    import cleaning.beadsubtraction as B
    B.BeadSubtractionTask = BeadSubtractionTask
    beads  = next(iter(create(TrackReaderTask(path = utpath("fixedbeads.pk"))).run()))
    lst    = FixedBeadDetection()(beads)
    assert len(lst) == 1
    assert lst[0][-1] == 4
    frames = FixedBeadDetection().dataframe(beads)
    assert frames.shape == (4, 16)
    assert set(frames[frames.good].bead.values) == {4}

def test_clippingtask():
    "tests clipping task"
    track = Track(**(Experiment(baseline = None, thermaldrift = None)
                     .track(1, 5, seed = 0)))
    arr   = np.copy(track.data[0])
    assert np.all(np.isfinite(arr))
    ClippingTask()(track, 0, arr)
    assert_equal(arr, track.data[0])

    extr = np.min(arr), np.max(arr)
    cyc  = track.cycles.withphases(5)

    cyc[0,0][10] = extr[0]-.1
    cyc[0,0][12] = extr[1]+.001
    cyc[0,1][10] = extr[0]-.1
    cyc[0,1][12] = extr[1]+.001
    cyc[0,2][12] = np.NaN

    arr = np.copy(track.data[0])
    ClippingTask()(track, 0, arr)
    cyc = cyc.withdata({0: arr})
    assert_equal(np.nonzero(np.isnan(cyc[0,0]))[0], [10, 12])
    assert_equal(np.nonzero(np.isnan(cyc[0,1]))[0], [10, 12])
    nzer = np.nonzero(arr-track.data[0])[0]
    assert len(nzer) == 5
    assert np.all(np.isnan(arr[nzer]))

def test_rescaling():
    "test rescaling"
    attrs = (
        'mindeltavalue', 'cstmaxderivate',
        'maxabsvalue', 'maxderivate',
        'minhfsigma', 'maxhfsigma',
        'minextent', 'maxextent',
        'mindifference', 'maxdisttozero'
    )

    task = DataCleaningTask()
    new  = task.rescale(5.)
    resc = new.__getstate__()
    assert task is not new
    for i, j in task.__getstate__().items():
        assert abs(resc[i]-j*5) < 1e-6 if i in attrs else resc[i] == j

    for cls in (ClippingTask, BeadSubtractionTask):
        task = cls()
        new  = task.rescale(5.)
        assert task is not new
        assert task == new

    obj   = FixedBeadDetection()
    new   = obj.rescale(5)
    assert obj is not new

    attrs = ('maxabsvalue', 'maxderivate', 'mindeltavalue', 'cstmaxderivate')
    for i, j in obj.abberrant.__getstate__().items():
        assert abs(new.abberrant.__getstate__()[i] - (j*5. if i in attrs else j)) < 1e-5

    attrs = ('mindzdt',)
    for i, j in obj.drops.__dict__.items():
        assert getattr(new.drops, i) == (j*5. if i in attrs else j)

    attrs = ('maxdiff', 'minhfsigma', 'maxhfsigma', 'maxextent')
    for i, j in obj.__dict__.items():
        if not np.isscalar(j):
            continue
        assert abs(getattr(new, i) - (j*5. if i in attrs else j)) < 1e-5

if __name__ == '__main__':
    test_rescaling()
