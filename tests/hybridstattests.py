#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"testing hybridstat"
# pylint: disable=import-error,no-name-in-module
from pathlib                        import Path
from tempfile                       import mktemp, gettempdir
from numpy.testing                  import assert_allclose
from peakcalling.tohairpin          import np, Hairpin, PEAKS_DTYPE
from peakcalling.processor          import ByHairpinGroup, ByHairpinBead, Distance
from data                           import Track
from utils                          import EVENTS_DTYPE
from hybridstat.reporting           import (run, HybridstatExcelProcessor,
                                            HybridstatExcelTask)
from hybridstat.reporting.identification  import writeparams, readparams
from hybridstat.reporting.batch           import (HybridstatBatchTask,
                                                  computereporters)
from control.taskcontrol            import create
from testingcore                    import path as utfilepath

def test_excel():
    "tests reporting"
    for path in Path(gettempdir()).glob("*_hybridstattest*.*"):
        path.unlink()
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

def test_ids():
    "tests identifications"
    for path in Path(gettempdir()).glob("*_hybridstattest*.xlsx"):
        path.unlink()

    out = mktemp()+"_hybridstattest10.xlsx"
    assert not Path(out).exists()
    writeparams(out, [('hp1', (1, 3, 5)), ('hp2', (10,)), ('hp3', tuple())])
    assert Path(out).exists()
    res = readparams(out)
    assert set(res) == {(1, 'hp1'), (3, 'hp1'), (5, 'hp1'), (10, 'hp2')}

    res = readparams(utfilepath('hybridstat_report.xlsx'))
    assert len(res) == 2
    val = next(i for i in res if i[0] == 0)
    assert val[:2] == (0, 'GF4')
    assert_allclose(val[2:], [1173.87, 1.87], atol = 2e-2)

def test_excelprocessor():
    "tests reporting processor"
    for path in Path(gettempdir()).glob("*_hybridstattest*.xlsx"):
        path.unlink()
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
        new = lambda self, _: self
        withdata = lambda self, fcn: fcn(self)

        @staticmethod
        def values():
            "-"
            tmp2   = np.array([(5, np.zeros(5)), (5, np.zeros(5))],
                              dtype = EVENTS_DTYPE)
            evts1  = [(0.,  np.array([None, None, None])),
                      (.01, np.array([None, (0, np.zeros(5)), tmp2])),
                      (.1,  np.array([None, None, (0, np.zeros(5))])),
                      (.5,  np.array([None, None, tmp2])),
                      (1.,  np.array([None, None, (0, np.zeros(5))]))]
            return [ByHairpinGroup('hp100',
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


    task = HybridstatExcelTask(path      = mktemp()+"_hybridstattest2.xlsx",
                               hairpins  = {'hp100': Hairpin(peaks = truth[0]),
                                            'hp101': Hairpin(peaks = truth[1])},
                               sequences = sequences,
                               oligos    = ['atgc'],
                               knownbeads= (98,),
                               minduration= 2)
    proc = HybridstatExcelProcessor(task)
    # pylint: disable=missing-docstring
    class _Runner:
        model = {1:2}
        @staticmethod
        def apply(fcn):
            fcn(_Frame())

        @property
        def data(self):
            return  self

        @staticmethod
        def poolkwargs(_):
            return {'pool': None, 'data': _Runner}

    assert not Path(task.path).exists()
    proc.run(_Runner())
    assert Path(task.path).exists()

def test_processor():
    "tests processor"
    for path in Path(gettempdir()).glob("*_hybridstattest*.xlsx"):
        path.unlink()
    out   = mktemp()+"_hybridstattest3.xlsx"

    task  = HybridstatBatchTask()
    task.addpaths(track    = (Path(utfilepath("big_legacy")).parent/"*.trk",
                              utfilepath("CTGT_selection")),
                  reporting= out,
                  sequence = utfilepath("hairpins.fasta"))

    pair = create((task,))
    assert not Path(out).exists()
    gen  = pair.run()
    assert not Path(out).exists()
    items = tuple(i for i in gen)
    items = tuple(tuple(i) for i in items)
    assert Path(out).exists()

def test_reporting():
    "tests processor"
    for path in Path(gettempdir()).glob("*_hybridstattest*.*"):
        path.unlink()
    out   = mktemp()+"_hybridstattest5.xlsx"

    tasks = computereporters(dict(track    = (Path(utfilepath("big_legacy")).parent/"*.trk",
                                              utfilepath("CTGT_selection")),
                                  reporting= out,
                                  sequence = utfilepath("hairpins.fasta")))

    itms = next(tasks)
    assert not Path(out).exists()
    tuple(itms)
    assert Path(out).exists()

if __name__ == '__main__':
    test_excelprocessor()
