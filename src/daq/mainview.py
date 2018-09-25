#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All view pieces are brought together"
import bokeh.layouts as     layouts # pylint: disable=useless-import-alias
from .beadstableview import BeadsTableView
from .camera         import DAQCameraView
from .fovtableview   import FoVTableView
from .timeseries     import BeadTimeSeriesView

class MainView:
    "All view pieces are brought together"
    def __init__(self, **_):
        self._beads  = BeadsTableView    (**_)
        self._cam    = DAQCameraView     (**_)
        self._fov    = FoVTableView      (**_)
        self._series = BeadTimeSeriesView(**_)

    def observe(self, ctrl):
        """
        observe the controller
        """
        for i in self.__dict__.values():
            i.observe(ctrl)

    def ismain(self, ctrl):
        "nothing to do"

    def addtodoc(self, ctrl, doc):
        """
        add bokeh items
        """
        itms = {i[1:]: j.addtodoc(ctrl, doc) for i, j in self.__dict__.items()}
        assert all(len(i) == 1 for i in itms.values())

        mod  = dict(sizing_mode = ctrl.theme.get('main', 'sizingmode', 'fixed'))
        row  = layouts.row([itms['beads'][0], itms["fov"][0]], **mod)
        col  = layouts.column([itms['series'][0], row], **mod)
        return [layouts.row([col, itms['cam'][0]], **mod)]
