#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,wildcard-import,unused-wildcard-import
# pylint: disable=wrong-import-position,ungrouped-imports,no-member
"Tests interval detection"
from IPython   import get_ipython # pylint:disable=import-error
assert get_ipython() is not None
from scripting import *
from scripting.jupyter import *

CLASSES = list(get_ipython().display_formatter.formatters['text/html'].type_printers.keys())

from data.views                                 import Beads, Cycles
from data.track                                 import Bead, FoV
from data.__scripting__.holoviewing.tracksdict  import TracksDictFovDisplayProperty
from peakfinding.processor.selector             import PeaksDict
from scripting.holoviewing                      import BasicDisplay

assert Beads                         in  CLASSES
assert Cycles                        in  CLASSES
assert Bead                          in  CLASSES
assert FoV                           in  CLASSES
assert PeaksDict                     in  CLASSES
assert BasicDisplay                  in  CLASSES
assert TracksDictFovDisplayProperty  in  CLASSES

HPIN   = ("gtcttttggtctttctggtgctcttcgaatAGCCTTCCAGCTGATATCTTCATAATAACCTATTACATATAAGCTTCAGG"
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
          "CAGCTTAATAACTAAGAAGATAATATCATAACATAGAAGGATAATGGACTTGGTGCgcttGCCACTTGAAGAttttt").lower()

REFS   = ("gccttacaca,gcctaatacc,cgtacggtta,acggatctca,aacatgaagg,"
          "cattctcagg,cagaatagct,accttctagg,cctaactgta,taacacgtcc,"
          "cctatcatgg,cgcatacaca").split(',')
CLEAN = TracksDict("../tests/testingcore/100bp_4mer/*.pk", # type: ignore
                   match = r".*/(.*)\.pk")
CLEAN.cleaned = True

def _test(txt, *itms):
    fcn = lambda x: str(x).replace('\n', '').replace(' ', '')
    txt = fcn(txt)
    for itm in itms:
        assert fcn(itm) == fcn(txt)

_test("""
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
      """, CLEAN.fov.display()['ref'])

_test("""
      :Overlay
         .Text.I  :Text   [frames,z]
         .Curve.I :Curve   [frames]   (z)
      """,
      CLEAN.cycles.display()['ref', 12],
      CLEAN.cycles[...,25].display()['ref', 25],
      CLEAN.cleancycles.display()['ref', 12],
      CLEAN.measures.display()['ref', 12],
      CLEAN.events.display()['ref', 12])

REF  = CLEAN['ref'].apply(Tasks.alignment,       # type: ignore
                          Tasks.eventdetection,  # type: ignore
                          Tasks.peakselector)    # type: ignore
_test("""
      :Overlay
         .Curve.Histogram   :Curve   [z]   (events)
         .Scatter.Histogram :Scatter   [z]   (events)
         .Scatter.Peaks     :Scatter   [z]   (events)
         .Curve.Peaks       :Curve   [z]   (events)
         .Curve.Sequence    :Curve   [z]   (events)
      """,
      (REF
       .display(sequence=HPIN, oligos=REFS, fit = False)
       .display())[25, 'hairpin 1', 1/8.8e-4, 0.])

_test("""
      :Overlay
         .Hairpin_1.Histogram.I  :Curve   [z]   (events)
         .Hairpin_1.Histogram.II :Scatter   [z]   (events)
         .Hairpin_1.Peaks.I      :Scatter   [z]   (events)
         .Hairpin_1.Peaks.II     :Curve   [z]   (events)
         .Curve.Sequence         :Curve   [z]   (events)
         .Text.I                 :Text   [z,events]
      """,
      REF.display(sequence=HPIN, oligos=REFS, fit = True).display()[25])

DMAP = CLEAN.peaks[['AACG', 'CCTC'], [12, 25]](format = None, reference = 'ref').display()
_test("""
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
      """, DMAP['AACG',12], DMAP['CCTC',25])

DMAP = CLEAN.peaks[['AACG', 'CCCC'], [12, 25]](format = '1d', reference = 'ref').display()
_test("""
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
      """, DMAP[12], DMAP[25])

DMAP = CLEAN.peaks[['AACG', 'CCTC'], [12, 25]](format = '1d', reference = 'ref').display()
_test("""
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
      """, DMAP[12], DMAP[25])

DMAP = CLEAN.peaks[['AACG', 'CCCC'], [12, 25]](format = '2d', reference = 'ref').display()
_test("""
      :Overlay
         .QuadMesh.I  :QuadMesh   [z,key]   (events)
         .Curve.Ref   :Curve   [z]   (key)
         .Curve.Peaks :Curve   [z]   (key)
         .Text.I      :Text   [z,key]
         .Text.II     :Text   [z,key]
         .Text.III    :Text   [z,key]
      """, DMAP[12], DMAP[25])

DMAP = CLEAN.peaks[['AACG', 'CCTC'], [12, 25]](format = '2d', reference = 'ref').display()
_test("""
      :Overlay
         .QuadMesh.I  :QuadMesh   [z,key]   (events)
         .Curve.Ref   :Curve   [z]   (key)
         .Curve.Peaks :Curve   [z]   (key)
         .Text.I      :Text   [z,key]
         .Text.II     :Text   [z,key]
         .Text.III    :Text   [z,key]
      """, DMAP[12], DMAP[25])
