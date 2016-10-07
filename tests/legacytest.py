#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests legacy data """

import unittest
import legacy

class RecordIO(unittest.TestCase):
    u"tests opening a trackfile"
    def test_opentrack_big(self):
        u"test a big track file"
        path = "../tests/data/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk"

        trk  = legacy.readtrack(path)
        self.assertEqual(trk['cyclemin'], 3)
        self.assertEqual(trk['cyclemax'], 104)
        self.assertEqual(trk['nphases'],  8)
        self.assertEqual(trk['t'].size,     49802)
        self.assertEqual(trk['zmag'].size,  49802)
        for i in range(39):
            self.assertEqual(trk[i].size,  49802)
        self.assertEqual(frozenset(x for x in trk if isinstance(x, int)),
                         frozenset([x for x in range(39)]))

    def test_opentrack_small(self):
        u"test a small track file"
        trk  = legacy.readtrack("../tests/data/test035_5HPs_mix_GATG_5nM_25C_8sec_with_ramp.trk")
        self.assertEqual(trk['cyclemin'], 3)
        self.assertEqual(trk['cyclemax'], 3)
        self.assertEqual(trk['nphases'],  8)
        self.assertEqual(trk['t'].size,     498)
        self.assertEqual(trk['zmag'].size,  498)
        for i in range(39):
            self.assertEqual(trk[i].size,  498)
        self.assertEqual(frozenset(x for x in trk if isinstance(x, int)),
                         frozenset([x for x in range(92)]))

    def test_opentrack_missing(self):
        u"test a missing track file"
        trk  = legacy.readtrack("___non__existant__track.trk")
        self.assertTrue(trk is None)

if __name__ == '__main__':
    unittest.main()
