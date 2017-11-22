#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=no-member,too-many-statements
"testing globals"
import pytest
from model.globals import Globals, LocalContext

def test_globals():
    "testing globals"
    ctrl = Globals()
    ctrl.addGlobalMap("toto", titi = 1)
    assert ctrl.getGlobal("toto").titi.get() == 1
    assert ctrl.getGlobal("toto").titi == 1

    ctrl.getGlobal("toto").titi = 2
    assert ctrl.getGlobal("toto").titi.get() == 2
    assert ctrl.getGlobal("toto").titi == 2

    ctrl.updateGlobal("toto", titi = 3)
    assert ctrl.getGlobal("toto").titi.get() == 3
    assert ctrl.getGlobal("toto").titi  == 3

    ctrl.updateGlobal("toto", titi = 3)
    assert ctrl.getGlobal("toto").titi  == 3
    del ctrl.getGlobal("toto")['titi']
    assert ctrl.getGlobal("toto").titi == 1

    del ctrl.getGlobal("toto").titi
    assert ctrl.getGlobal("toto").titi == 1

    ctrl.updateGlobal("toto", titi = 3)
    assert ctrl.getGlobal("toto").titi  == 3
    ctrl.getGlobal("toto").pop("titi")
    assert ctrl.getGlobal("toto").titi == 1

    ctrl.getGlobal("toto").toto.a.default = 2
    assert ctrl.getGlobal("toto").toto.a == 2

    ctrl.getGlobal("toto").toto.a = 3
    assert ctrl.getGlobal("toto").toto.a == 3

    del ctrl.getGlobal("toto").toto.a
    assert ctrl.getGlobal("toto").toto.a == 2

    with pytest.raises(KeyError):
        ctrl.getGlobal("toto").mm.pp = 1

def test_local():
    "testing local context"
    ctrl = Globals()
    ctrl.addGlobalMap("toto", titi = 1, tata = 1, toto = 1, tutu = 1)
    ctrl.getGlobal("toto").titi = 2
    ctrl.getGlobal("toto").toto = 2

    with LocalContext(ctrl).replace(toto = dict(titi = 3, tata = 2)):
        assert ctrl.getGlobal("toto").titi == 3
        assert ctrl.getGlobal("toto").tata == 2
        assert ctrl.getGlobal("toto").toto == 1
        assert ctrl.getGlobal("toto").tutu == 1
        ctrl.getGlobal("toto").tutu = 3
        ctrl.getGlobal("toto").toto = 3
        assert ctrl.getGlobal("toto").tutu == 3
        assert ctrl.getGlobal("toto").toto == 3

    assert ctrl.getGlobal("toto").titi == 2
    assert ctrl.getGlobal("toto").tata == 1
    assert ctrl.getGlobal("toto").toto == 2
    assert ctrl.getGlobal("toto").tutu == 1

    with LocalContext(ctrl).update(toto = dict(titi = 3, tata = 2)):
        assert ctrl.getGlobal("toto").titi == 3
        assert ctrl.getGlobal("toto").tata == 2
        assert ctrl.getGlobal("toto").toto == 2
        assert ctrl.getGlobal("toto").tutu == 1
        ctrl.getGlobal("toto").tutu = 3
        ctrl.getGlobal("toto").toto = 3
        assert ctrl.getGlobal("toto").tutu == 3
        assert ctrl.getGlobal("toto").toto == 3

    assert ctrl.getGlobal("toto").titi == 2
    assert ctrl.getGlobal("toto").tata == 1
    assert ctrl.getGlobal("toto").toto == 2
    assert ctrl.getGlobal("toto").tutu == 1
if __name__ == '__main__':
    test_local()
