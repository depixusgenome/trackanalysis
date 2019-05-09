#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,wildcard-import,unused-wildcard-import
# pylint: disable=wrong-import-position,ungrouped-imports,no-member,invalid-name
# pylint: disable=unused-argument,unused-import,no-name-in-module
"Tests interval detection"
import os
import warnings
from   concurrent.futures import ProcessPoolExecutor
import pytest
from   tests.testutils import integrationmark


def _comp(txt, *itms):
    fcn = lambda x: str(x).replace('\n', '').replace(' ', '')
    txt = fcn(txt)
    for itm in itms:
        assert fcn(itm) == fcn(txt)

def _callbacks():
    import scripting
    from IPython   import get_ipython # pylint:disable=import-error,wrong-import-order
    from data.views                                 import Beads, Cycles
    from data.track                                 import Bead, FoV
    from data.__scripting__.holoviewing.tracksdict  import TracksDictFovDisplayProperty
    from peakfinding.processor.selector             import PeaksDict
    CLASSES = list(
        get_ipython()
        .display_formatter
        .formatters['text/html']
        .type_printers
        .keys()
    )
    assert Beads                         in  CLASSES
    assert Cycles                        in  CLASSES
    assert Bead                          in  CLASSES
    assert FoV                           in  CLASSES
    assert PeaksDict                     in  CLASSES
    assert TracksDictFovDisplayProperty  in  CLASSES

def _data():
    from scripting import TracksDict
    tracks = TracksDict( # type: ignore
        "../data/100bp_4mer/*.pk",
        match = r".*/(.*)\.pk"
    )
    tracks.cleaned = True
    return tracks

def _holoviewing():
    tracks = _data()
    _comp("""
          :Overlay
             .Image.I    :Image   [x (μm),y (μm)]   (z)
             .Points.I   :Points   [x (μm),y (μm)]
             .Text.I     :Text   [x (μm),y (μm)]
             .Text.II    :Text   [x (μm),y (μm)]
             .Text.III   :Text   [x (μm),y (μm)]
             .Text.IV    :Text   [x (μm),y (μm)]
             .Text.V     :Text   [x (μm),y (μm)]
             .Text.VI    :Text   [x (μm),y (μm)]
             .Text.VII   :Text   [x (μm),y (μm)]
             .Text.VIII  :Text   [x (μm),y (μm)]
             .Text.IX    :Text   [x (μm),y (μm)]
             .Text.X     :Text   [x (μm),y (μm)]
             .Text.XI    :Text   [x (μm),y (μm)]
             .Text.XII   :Text   [x (μm),y (μm)]
             .Text.XIII  :Text   [x (μm),y (μm)]
             .Text.XIV   :Text   [x (μm),y (μm)]
             .Text.XV    :Text   [x (μm),y (μm)]
             .Text.XVI   :Text   [x (μm),y (μm)]
             .Text.XVII  :Text   [x (μm),y (μm)]
             .Text.XVIII :Text   [x (μm),y (μm)]
             .Text.XIX   :Text   [x (μm),y (μm)]
             .Text.XX    :Text   [x (μm),y (μm)]
             .Text.XXI   :Text   [x (μm),y (μm)]
             .Text.XXII  :Text   [x (μm),y (μm)]
             .Text.XXIII :Text   [x (μm),y (μm)]
             .Text.XXIV  :Text   [x (μm),y (μm)]
          """, tracks.fov.display()['ref'])

    _comp("""
          :Overlay
             .Text.I  :Text   [frames,z]
             .Curve.I :Curve   [frames]   (z)
          """,
          tracks.cycles.display()['ref', 12],
          tracks.cycles[...,25].display()['ref', 25],
          tracks.cleancycles.display()['ref', 12],
          tracks.measures.display()['ref', 12],
          tracks.events.display()['ref', 12])

def _holoviewing_hpin():
    from scripting import Tasks
    tracks = _data()
    ref    = tracks['ref'].apply(
        Tasks.alignment,    # type: ignore
        Tasks.eventdetection,  # type: ignore
        Tasks.peakselector     # type: ignore
    )
    hpin   = (
        "gtcttttggtctttctggtgctcttcgaatAGCCTTCCAGCTGATATCTTCATAATAACCTATTACATATAAGCTTCAGG"
        "CTATACACCTTCAATGCCTATAACTAAGCGTAACATACCAGGTCCAATTACACAGCCTTACACACATATCTGGACTTGGT"
        "GCCTAATACCAGAATCATTATACTAGATTGATTCTTCCTTAATACCTAACAATCTAGCCAGGATAACACATATACCAGCC"
        "TATACACGGACCATTGTTACGGAAGGTTAGCCATAATATCTTAACCGTCCTAAAGCCTTCCAGCGTTGCTCCCCCGCCCT"
        "CGATGTCACTACCCACCCTCCCCGCAGCAAGACATCGTTCGACCCTCTCCCCACTGCTCGCCCGCAACGAACCCTCACCC"
        "ACTCATCCTAGCAGATATCATAGGATACACGGAAGTACCGTACGGTTATATACAATCATATAGGCATACTATAAcacgGA"
        "TCTCAGCCTGGTTATATATATCATAACATACACAGATACACGGAAGCCGGACTTGGTGCATATAACAGGTAAGTAATCTA"
        "ATCAATAACTAATCATAACACAGCTATACATAGATAACCTAACATAATCTTAGAATTAACATGAAGGATTAACACCGGAT"
        "ACACATTCTCAGGTACCAATACAGTACTAATAGCCAACATCCTAGCAGCGTTGCTCCCCCGCCCTCGATGTCACTACCCA"
        "CCCTCCCCGCAGCAAGACATCGTTCGACCCTCTCCCCACTGCTCGCCCGCAACGAACCCTCACCCACTCATCCTAGCAGA"
        "TTAACCATTACATAGATATACAGAATAGCTTCTAACATAACCTAATAACCAATAACCTTCTAGGCCTGATACACACCGGC"
        "CATTACTAAGTACACCTAATAACCGTACATACAGAATGGACTTGGTGCGTACTATGTAAccagATAAGATCATAACCTAA"
        "CTGTATCCAATAATCTAATCCTAACATGGTACTAGATAACACGTCCATACGTAACACAATGCCAATTACCAGGACTTGGT"
        "GCCGTTGCTCCCCCGCCCTCGATGTCACTACCCACCCTCCCCGCAGCAAGACATCGTTCGACCCTCTCCCCACTGCTCGC"
        "CCGCAACGAACCCTCACCCACTGACTTGGTGCCAATCTGTAACCATAAGGCCTAATAGCTAAGATACACCAGCGCATAAT"
        "CCTTACCATACCTAGCCTAACTCAGATAGCGTCCTTACACACATTGATACTGATCCAGCCGTCCTTACATACCTATCATG"
        "GACTTGGTGCATTCAATACGCATACACATTCCATAACCGGTTAACTTACTTCCATACAATCCAATATAACACAGCGCTAT"
        "CAGCTTAATAACTAAGAAGATAATATCATAACATAGAAGGATAATGGACTTGGTGCgcttGCCACTTGAAGAttttt"
    ).lower()
    refs   = ("gccttacaca,gcctaatacc,cgtacggtta,acggatctca,aacatgaagg,"
              "cattctcagg,cagaatagct,accttctagg,cctaactgta,taacacgtcc,"
              "cctatcatgg,cgcatacaca").split(',')

    _comp("""
          :Overlay
             .Curve.Histogram   :Curve   [z]   (events)
             .Scatter.Histogram :Scatter   [z]   (events)
             .Scatter.Peaks     :Scatter   [z]   (events)
             .Curve.Peaks       :Curve   [z]   (events)
             .Curve.Sequence    :Curve   [z]   (events)
          """,
          (ref
           .display(sequence=hpin, oligos=refs, fit = False)
           .display())[25, 'hairpin 1', 1/8.8e-4, 0.])

    _comp("""
          :Overlay
             .Hairpin_1.Histogram.I  :Curve   [z]   (events)
             .Hairpin_1.Histogram.II :Scatter   [z]   (events)
             .Hairpin_1.Peaks.I      :Scatter   [z]   (events)
             .Hairpin_1.Peaks.II     :Curve   [z]   (events)
             .Curve.Sequence         :Curve   [z]   (events)
             .Text.I                 :Text   [z,events]
          """,
          ref.display(sequence=hpin, oligos=refs, fit = True).display()[25])

def _holoviewing_ref_1d(tpe):
    from scripting import Tasks
    tracks = _data()
    if tpe == 1:
        dmap = tracks.peaks[['AACG', 'CCTC'], [12, 25]](format = None, reference = 'ref').display()
        _comp("""
              :Overlay
                 .Area.Ref    :Area   [z]   (events)
                 .Curve.Ref   :Curve   [z]   (events)
                 .Scatter.Ref :Scatter   [z]   (events)
                 .Scatter.I   :Scatter   [z]   (events)
                 .Curve.I     :Curve   [z]   (events)
                 .Curve.Key   :Curve   [z]   (events)
                 .Scatter.Key :Scatter   [z]   (events)
                 .Scatter.II  :Scatter   [z]   (events)
                 .Curve.II    :Curve   [z]   (events)
                 .Text.I      :Text   [z,events]
              """, dmap['AACG',12], dmap['CCTC',25])

    elif tpe == 2:
        dmap = tracks.peaks[['AACG', 'CCCC'], [12, 25]](format = '1d', reference = 'ref').display()
        _comp("""
              :Overlay
                 .Area.Ref     :Area   [z]   (events)
                 .Curve.Ref    :Curve   [z]   (events)
                 .Scatter.Ref  :Scatter   [z]   (events)
                 .Scatter.I    :Scatter   [z]   (events)
                 .Curve.I      :Curve   [z]   (events)
                 .Curve.AACG   :Curve   [z]   (events)
                 .Scatter.AACG :Scatter   [z]   (events)
                 .Scatter.II   :Scatter   [z]   (events)
                 .Curve.II     :Curve   [z]   (events)
                 .Curve.CCCC   :Curve   [z]   (events)
                 .Scatter.CCCC :Scatter   [z]   (events)
                 .Scatter.III  :Scatter   [z]   (events)
                 .Curve.III    :Curve   [z]   (events)
                 .Text.I       :Text   [z,events]
              """, dmap[12], dmap[25])

    else:
        dmap = tracks.peaks[['AACG', 'CCTC'], [12, 25]](format = '1d', reference = 'ref').display()
        _comp("""
              :Overlay
                 .Area.Ref     :Area   [z]   (events)
                 .Curve.Ref    :Curve   [z]   (events)
                 .Scatter.Ref  :Scatter   [z]   (events)
                 .Scatter.I    :Scatter   [z]   (events)
                 .Curve.I      :Curve   [z]   (events)
                 .Curve.AACG   :Curve   [z]   (events)
                 .Scatter.AACG :Scatter   [z]   (events)
                 .Scatter.II   :Scatter   [z]   (events)
                 .Curve.II     :Curve   [z]   (events)
                 .Curve.CCTC   :Curve   [z]   (events)
                 .Scatter.CCTC :Scatter   [z]   (events)
                 .Scatter.III  :Scatter   [z]   (events)
                 .Curve.III    :Curve   [z]   (events)
                 .Text.I       :Text   [z,events]
              """, dmap[12], dmap[25])

def _holoviewing_ref_2d():
    from scripting import Tasks
    tracks = _data()
    dmap = tracks.peaks[['AACG', 'CCCC'], [12, 25]](format = '2d', reference = 'ref').display()
    _comp("""
          :Overlay
             .QuadMesh.I  :QuadMesh   [z,key]   (events)
             .Curve.Ref   :Curve   [z]   (key)
             .Curve.Peaks :Curve   [z]   (key)
             .Text.I      :Text   [z,key]
             .Text.II     :Text   [z,key]
             .Text.III    :Text   [z,key]
          """, dmap[12], dmap[25])

    dmap = tracks.peaks[['AACG', 'CCTC'], [12, 25]](format = '2d', reference = 'ref').display()
    _comp("""
          :Overlay
             .QuadMesh.I  :QuadMesh   [z,key]   (events)
             .Curve.Ref   :Curve   [z]   (key)
             .Curve.Peaks :Curve   [z]   (key)
             .Text.I      :Text   [z,key]
             .Text.II     :Text   [z,key]
             .Text.III    :Text   [z,key]
          """, dmap[12], dmap[25])

def _processrun(fcn, *args):
    from tests.testutils.modulecleanup import modulecleanup
    for _ in modulecleanup(pairs = [('ACCEPT_SCRIPTING', 'jupyter')]):
        fcn(*args)

def _run_holoviewing(fcn, *args):
    headless         = (
        os.environ.get("DPX_TEST_HEADLESS", '').lower().strip() in ('true', '1', 'yes')
        or 'DISPLAY' not in os.environ
    )
    with warnings.catch_warnings():
        for i in [
                ".*Using or importing the ABCs from 'collections'.*",
                ".*In future, it will be an error for 'np.bool_.*",
                ".*he truth value of an.*"
        ]:
            warnings.filterwarnings(
                'ignore',
                category = DeprecationWarning,
                message  = i
            )

        if headless:
            with ProcessPoolExecutor(1) as pool:
                pool.submit(_processrun, fcn, *args).result(timeout = 120)
        else:
            _processrun(fcn, *args)

@integrationmark
def test_holoviewing_callbacks():
    "test jupyter callbacks"
    _run_holoviewing(_callbacks)

@integrationmark
def test_holoviewing_simple():
    "test simple graphs"
    _run_holoviewing(_holoviewing)

@integrationmark
def test_holoviewing_hpin():
    "test hpin graphs"
    _run_holoviewing(_holoviewing_hpin)

@integrationmark
def test_holoviewing_ref2d():
    "test hpin graphs"
    _run_holoviewing(_holoviewing_ref_2d)

@integrationmark
@pytest.mark.parametrize("tpe", [1, 2, 3])
def test_holoviewing_ref1d(tpe):
    "test hpin graphs"
    _run_holoviewing(_holoviewing_ref_1d, tpe)

if __name__ == '__main__':
    test_holoviewing_simple()
