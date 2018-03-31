#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All view pieces are brought together"
import bokeh.layouts as     layouts
from .beadstableview import BeadsTableView
from .camera         import DAQCameraView
from .fovtableview   import FoVTableView
from .timeseries     import BeadTimeSeriesView

class MainView:
    "All view pieces are brought together"
    def __init__(self, ctrl = None):
        self._beads  = BeadsTableView    (ctrl = ctrl)
        self._cam    = DAQCameraView     (ctrl = ctrl)
        self._fov    = FoVTableView      (ctrl = ctrl)
        self._series = BeadTimeSeriesView(ctrl = ctrl)

    def observe(self, ctrl):
        """
        observe the controller
        """
        for i in self.__dict__.items():
            i.observe(ctrl)

    def ismain(self):
        "nothing to do"

    def addtodoc(self, ctrl, doc):
        """
        add bokeh items
        """
        itms = {i[1:]: j.addtodoc(ctrl, doc) for i, j in self.__dict__.items()}
        assert all(len(i) == 1 for i in itms.values())

        mod  = dict(sizing_mode = ctrl.theme.get('main', 'sizingmode', 'fixed'))
        return [layouts.layout([(itms["series"][0], itms["fov"][0]),
                                (itms["cam"][0],    itms["beads"][0])], **mod)]
