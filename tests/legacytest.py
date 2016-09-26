u""" Tests legacy data """

import unittest

class RecordIO(unittest.TestCase):
    u"tests opening a trackfile"
    def test_opentrack(self):
        import legacy
        print(legacy.readtrack("../data/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk"))

if __name__ == '__main__':
    unittest.main()
