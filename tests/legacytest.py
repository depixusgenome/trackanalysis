u""" Tests legacy data """

import unittest

class RecordIO(unittest.TestCase):
    u"tests opening a trackfile"
    def test_opentrack(self):
        import legacy
        print(legacy.open("data/test035_5HP_mix_AAGC_5nM_25C_20sec.trk"))
