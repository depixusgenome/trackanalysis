#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Testing DAQ"
import numpy         as     np
from   numpy.testing import assert_equal
from daq.data        import RoundRobinVector, BeadsRoundRobinVector
from daq.model       import DAQRamp, DAQIdle
from daq.control     import DAQController

def test_roundrobin():
    "test round robin"
    dtype = np.dtype('f4,f4,f4')
    vect  = RoundRobinVector(10, dtype)
    assert vect.view().dtype == dtype
    assert vect.view().size  == 0

    truth = np.arange(160, dtype = 'f4').view('f4,f4,f4')
    vect.append(truth[:1])
    assert_equal(vect.view(), truth[:1])

    vect.append(truth[1:6])
    assert_equal(vect.view(), truth[:6])

    vect.append(truth[6:12])
    assert_equal(vect.view(), truth[2:12])

    vect.append(truth[12:21])
    assert_equal(vect.view(), truth[11:21])

    vect.append(truth[21:30])
    assert_equal(vect.view(), truth[20:30])

    vect.append(truth[30:39])
    assert_equal(vect.view(), truth[29:39])

    base  = np.dtype([('t', 'I8'), ('x', 'f4'), ('y', 'f4')])
    beads = BeadsRoundRobinVector.fulltype(3, base)
    assert beads == np.dtype([('t', 'I8'),
                              ('x0', 'f4'), ('y0', 'f4'),
                              ('x1', 'f4'), ('y1', 'f4'),
                              ('x2', 'f4'), ('y2', 'f4')])
    vect = BeadsRoundRobinVector(10, 3, base)
    assert vect.view().dtype == beads

    beads = np.dtype([('t', 'I8'),
                      ('x0', 'f4'), ('y0', 'f4'),
                      ('x1', 'f4'), ('y1', 'f4')])
    vect.nbeads = 2
    assert vect.view().dtype == beads

    beads = np.dtype([('t', 'I8'),
                      ('x0', 'f4'), ('y0', 'f4'),
                      ('x1', 'f4'), ('y1', 'f4'),
                      ('x2', 'f4'), ('y2', 'f4'),
                      ('x3', 'f4'), ('y3', 'f4')])
    vect.nbeads = 4
    assert vect.view().dtype == beads

def test_controller():
    "test controller"
    ctrl = DAQController()
    assert ctrl.data.fov.view().size == 0
    data = np.zeros(5, dtype = ctrl.data.fov.view().dtype)

    cnt = [0]
    def _onaddfovdata(**_):
        cnt[0] += 1
    ctrl.observe(_onaddfovdata)

    for i in range(1,3):
        ctrl.addfovdata(data)
        assert cnt[0] == i
        assert ctrl.data.fov.view().size == data.size*(i)

    cnt = [0]
    def _onaddbeaddata(**_):
        cnt[0] += 1
    ctrl.observe(_onaddbeaddata)

    for i in range(1,3):
        ctrl.addbeaddata(data)
        assert cnt[0] == i
        assert ctrl.data.beads.view().size == data.size*i

    cnt = [0]
    def _onupdateprotocol(**_):
        cnt[0] += 1
    ctrl.observe(_onupdateprotocol)

    assert isinstance(ctrl.config.protocol, DAQIdle)
    ctrl.updateprotocol(DAQRamp())
    assert isinstance(ctrl.config.protocol, DAQRamp)
    assert cnt[0] == 1
