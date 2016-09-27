u""" Tests legacy data """

import unittest

class RecordIO(unittest.TestCase):
    u"tests opening a trackfile"
    def test_opentrack(self):
        import legacy
        trk = legacy.readtrack("../data/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk")
        self.assertEqual(trk['cyclemin'], 3)
        self.assertEqual(trk['cyclemax'], 104)
        self.assertEqual(trk['nphases'],  8)
        self.assertEqual(trk['t'].size,     49802)
        self.assertEqual(trk['zmag'].size,  49802)
        for i in range(39):
            self.assertEqual(trk[i].size,  49802)
        self.assertEqual(frozenset(x for x in trk if isinstance(x, int)),
                         frozenset([x for x in range(39)]))


if __name__ == '__main__':
    unittest.main()
