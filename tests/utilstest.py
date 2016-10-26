#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Test utils"
# pylint: disable=import-error
import  unittest
from    utils.lazy import LazyInstError, LazyInstanciator, LazyDict


class LazyTest(unittest.TestCase):
    u"test lazy stuff"
    def test_instanciator_verify(self):
        u"test instanciator argument verifications"
        with self.assertRaises(LazyInstError):
            LazyInstError.verify(lambda x: None)
            LazyInstError.verify(1)
            LazyInstError.verify("")
        self.assertEqual(LazyInstError.verify(lambda *x, y = 1, **z: None), None)
        self.assertEqual(LazyInstError.verify(lambda y = 1, **z: None), None)
        self.assertEqual(LazyInstError.verify(lambda **z: None), None)

    def test_instanciator(self):
        u"test instanciator"
        lst = []
        class _AnyType:
            def __init__(self):
                lst.append(1)

        fcn  = lambda: _AnyType() # pylint: disable=unnecessary-lambda
        lazy = LazyInstanciator(fcn)
        self.assertEqual(len(lst), 0)

        ans  = lazy()
        self.assertEqual(len(lst), 1)

        ans2 = lazy()
        self.assertEqual(len(lst), 1)
        self.assertTrue(ans is ans2)

    def test_lazydict(self):
        u"test lazydict"
        lst = []

        def _create(name):
            def __init__(_):
                lst.append(name)
            return name, type(name, tuple(), dict(__init__ = __init__))

        for fcn in (iter, dict):
            dico = LazyDict(fcn((_create('l1'), _create('l2'))),
                            **dict((_create('l3'), _create('l4'))))
            self.assertEqual(len(lst), 0)

            self.assertTrue(dico['l1'].__class__.__name__, 'l1')
            self.assertEqual(lst, ['l1'])

            self.assertTrue(dico['l1'].__class__.__name__, 'l1')
            self.assertEqual(lst, ['l1'])

            self.assertTrue('l2' in dico)
            del dico['l2']
            self.assertFalse('l2' in dico)

            self.assertEqual(lst, ['l1'])

            self.assertTrue(dico.pop('l3').__class__.__name__, 'l3')
            self.assertEqual(lst, ['l1', 'l3'])

            self.assertEqual(dico.pop('l3', lambda:111),  111)
            self.assertEqual(lst, ['l1', 'l3'])

            self.assertTrue(dico.get(*_create('l7')).__class__.__name__, 'l7')
            self.assertEqual(lst, ['l1', 'l3', 'l7'])
            self.assertFalse('l7' in dico)

            self.assertEqual(dico.setdefault('l4', None).__class__.__name__, 'l4')
            self.assertEqual(lst, ['l1', 'l3', 'l7', 'l4'])
            self.assertEqual(dico.setdefault('l4', None).__class__.__name__, 'l4')
            self.assertEqual(lst, ['l1', 'l3', 'l7', 'l4'])

            self.assertEqual(dico.setdefault(*_create('l8')).__class__.__name__, 'l8')
            self.assertEqual(lst, ['l1', 'l3', 'l7', 'l4', 'l8'])
            self.assertTrue('l8' in dico)
            self.assertEqual(dico.setdefault('l8', None).__class__.__name__, 'l8')
            self.assertEqual(lst, ['l1', 'l3', 'l7', 'l4', 'l8'])
            self.assertTrue('l8' in dico)
            lst.clear()

if __name__ == '__main__':
    unittest.main()
