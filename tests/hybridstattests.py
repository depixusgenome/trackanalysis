#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"testing hybridstat"
# pylint: disable=import-error,no-name-in-module
from pathlib                import Path
from tempfile               import mktemp
from peakcalling.tohairpin  import np, Hairpin, PEAKS_DTYPE
from peakcalling.processor  import ByHairpinGroup, ByHairpinBead, Distance
from data                   import Track
from utils                  import EVENTS_DTYPE
from hybridstat.reporting   import run, HybridstatExcelProcessor, HybridstatExcelTask
from hybridstat.processor   import HybridstatTask
from control.taskcontrol    import create
from testingcore            import path

def test_excel():
    u"tests reporting"
    truth  = [np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/1e-3,
              np.array([0., .1, .5, 1.2, 1.5], dtype = 'f4')/1e-3]

    sequences = {'hp100': np.array(['c']*1500), 'hp101': np.array(['c']*1500)}
    for i in (100, 500, 1000):
        sequences['hp100'][i-3:i+1] = list('atgc')
    sequences['hp100'] = ''.join(sequences['hp100'])
    for i in (100, 500, 1200, 1000):
        sequences['hp101'][i-3:i+1] = list('atgc')
    sequences['hp101'] = ''.join(sequences['hp101'])

    tmp2   = np.array([(5, np.zeros(5)), (5, np.zeros(5))], dtype = EVENTS_DTYPE)
    evts1  = [(0.,  np.array([None, None, None])),
              (.01, np.array([None, (0, np.zeros(5)), tmp2])),
              (.1,  np.array([None, None, (0, np.zeros(5))])),
              (.5,  np.array([None, None, tmp2])),
              (1.,  np.array([None, None, (0, np.zeros(5))]))]
    groups = [ByHairpinGroup('hp100',
                             [ByHairpinBead(100, .95, Distance(.1, 1000., 0.0),
                                            np.array([(0., 0.),   (.01, np.iinfo('i4').min),
                                                      (.1, 100.), (.5, 500.),
                                                      (1., 1000.)], dtype = PEAKS_DTYPE),
                                            evts1)]),
              ByHairpinGroup(None,
                             [ByHairpinBead(101, -3, Distance(.1, 1000., 0.0),
                                            np.array([(0., 0.)], dtype = PEAKS_DTYPE),
                                            [(0., np.array([None, None, (0, np.zeros(5))]))]),
                              ByHairpinBead(102, -3, Distance(.1, 1000., 0.0),
                                            np.empty((0,), dtype = PEAKS_DTYPE),
                                            [])])]
    dat   = {100: np.arange(10)*.1, 101: np.arange(10)*.2,
             102: np.arange(10)*.3, 104: np.arange(10)*.2}
    cyc   = np.array([0,10,5,10,5,100,5,10,5]*3)
    track = Track(path      = "mypath",
                  data      = dat,
                  framerate = 1./30.,
                  phases    = (np.cumsum(cyc)-10).reshape((3,9)))
    fcn = lambda x: run(path      = x,
                        track     = track,
                        config    = "myconfig",
                        hairpins  = {'hp100': Hairpin(peaks = truth[0]),
                                     'hp101': Hairpin(peaks = truth[1])},
                        sequences = sequences,
                        oligos    = ['atgc'],
                        knownbeads= (98,),
                        minduration= 2,
                        groups    = groups)

    fname = mktemp()+"_hybridstattest.xlsx"
    assert not Path(fname).exists()
    fcn(fname)
    assert Path(fname).exists()

    fname = mktemp()+"_hybridstattest.csv"
    assert not Path(fname).exists()
    fcn(fname)
    assert Path(fname).exists()

    fname = mktemp()+"_hybridstattest.pkz"
    assert not Path(fname).exists()
    fcn(fname)
    assert Path(fname).exists()

def test_excelprocessor():
    u"tests reporting processor"
    truth  = [np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/1e-3,
              np.array([0., .1, .5, 1.2, 1.5], dtype = 'f4')/1e-3]

    sequences = {'hp100': np.array(['c']*1500), 'hp101': np.array(['c']*1500)}
    for i in (100, 500, 1000):
        sequences['hp100'][i-3:i+1] = list('atgc')
    sequences['hp100'] = ''.join(sequences['hp100'])
    for i in (100, 500, 1200, 1000):
        sequences['hp101'][i-3:i+1] = list('atgc')
    sequences['hp101'] = ''.join(sequences['hp101'])

    dat   = {100: np.arange(10)*.1, 101: np.arange(10)*.2,
             102: np.arange(10)*.3, 104: np.arange(10)*.2}
    cyc   = np.array([0,10,5,10,5,100,5,10,5]*3)

    class _Frame:
        track = Track(path      = "mypath",
                      data      = dat,
                      framerate = 1./30.,
                      phases    = (np.cumsum(cyc)-10).reshape((3,9)))
        def __iter__(self):
            tmp2   = np.array([(5, np.zeros(5)), (5, np.zeros(5))],
                              dtype = EVENTS_DTYPE)
            evts1  = [(0.,  np.array([None, None, None])),
                      (.01, np.array([None, (0, np.zeros(5)), tmp2])),
                      (.1,  np.array([None, None, (0, np.zeros(5))])),
                      (.5,  np.array([None, None, tmp2])),
                      (1.,  np.array([None, None, (0, np.zeros(5))]))]
            i =  [ByHairpinGroup('hp100',
                                 [ByHairpinBead(100, .95, Distance(.1, 1000., 0.0),
                                                np.array([(0., 0.),
                                                          (.01, np.iinfo('i4').min),
                                                          (.1, 100.),
                                                          (.5, 500.),
                                                          (1., 1000.)],
                                                         dtype = PEAKS_DTYPE),
                                                evts1)]),
                  ByHairpinGroup(None,
                                 [ByHairpinBead(101, -3, Distance(.1, 1000., 0.0),
                                                np.array([(0., 0.)],
                                                         dtype = PEAKS_DTYPE),
                                                [(0., np.array([None, None,
                                                                (0, np.zeros(5))]))]),
                                  ByHairpinBead(102, -3, Distance(.1, 1000., 0.0),
                                                np.empty((0,), dtype = PEAKS_DTYPE),
                                                [])])]
            return zip(range(len(i)), i)


    task = HybridstatExcelTask(path      = mktemp()+"_hybridstattest2.xlsx",
                               hairpins  = {'hp100': Hairpin(peaks = truth[0]),
                                            'hp101': Hairpin(peaks = truth[1])},
                               sequences = sequences,
                               oligos    = ['atgc'],
                               knownbeads= (98,),
                               minduration= 2)
    proc = HybridstatExcelProcessor(task)
    class _Runner:
        model = {1:2}
        @staticmethod
        def apply(fcn):
            u"doc"
            tuple(fcn(_Frame()))
    assert not Path(task.path).exists()
    proc.run(_Runner())
    assert Path(task.path).exists()

def test_processor():
    u"tests processor"
    out   = mktemp()+"_hybridstattest3.xlsx"

    task  = HybridstatTask()
    task.addpaths(track    = (Path(path("big_legacy")).parent/"*.trk",
                              path("CTGT_selection")),
                  reporting= out,
                  sequence = path("hairpins.fasta"))

    pair = create((task,))
    assert not Path(out).exists()
    gen  = pair.run()
    assert not Path(out).exists()
    items = tuple(i for i in gen)
    items = tuple(tuple(i) for i in items)
    assert Path(out).exists()

if __name__ == '__main__':
    test_processor()
