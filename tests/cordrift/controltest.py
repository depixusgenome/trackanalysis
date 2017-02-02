#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests that the cordrift processor runs correctly"

from cordrift.processor     import BeadDriftTask
from simulator.processor    import TrackSimulatorTask
from control.taskcontrol    import TaskPair

def test_process():
    u"tests that tracks are well simulated"
    pair = TaskPair.create((TrackSimulatorTask(brownian  = 0., randtargs = None),
                            BeadDriftTask()))
    elems = tuple(pair.run())
    print(tuple(tuple(x) for x in elems))

if __name__ == '__main__':
    test_process()
