#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"tests opening, reading and analysis of a ramp.trk file"
#from   legacy import readtrack   # pylint: disable=import-error,no-name-in-module
from control.taskcontrol import create
from model.task          import TrackReaderTask
from ramp.processor      import RampDataFrameTask
from testingcore         import path

def test_dataframe():
    "test ramp dataframe"
    next(create(TrackReaderTask(path = path("ramp_legacy")),
                RampDataFrameTask()).run())

if __name__ == '__main__':
    test_dataframe()
