#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"tests opening, reading and analysis of a ramp.trk file"
#from   legacy import readtrack   # pylint: disable=import-error,no-name-in-module
from taskcontrol.taskcontrol    import create
from taskmodel                  import TrackReaderTask
from ramp.processor             import RampStatsTask
from ramp.view._widget          import DpxRamp, Slider # pylint: disable=protected-access
from testingcore                import path
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import

def test_dataframe():
    "test ramp dataframe"
    next(create(TrackReaderTask(path = path("ramp_legacy")),
                RampStatsTask()).run())

def test_rampview(bokehaction): # pylint: disable=redefined-outer-name
    "test the view"
    done = [0]
    def _ondone(start = None, **_):
        if start:
            done[0] += 1
        else:
            done[0] -= 1

    with bokehaction.launch('ramp.view.RampPlotView', 'app.toolbar') as server:
        server.ctrl.display.observe("ramp.pool", _ondone)
        server.load('ramp_5HPs_mix.trk')

        assert 'config.tasks' not in server.savedconfig

        cnf = lambda: server.ctrl.theme.get("ramp", "dataframe")
        assert cnf().hfsigma == RampStatsTask.hfsigma
        server.change(DpxRamp, 'maxhfsigma', 0.006)
        server.wait()
        assert server.widget[DpxRamp].maxhfsigma == 0.006
        assert cnf().hfsigma[-1] == 0.006
        assert server.savedconfig['config.ramp']['dataframe'].hfsigma[-1] == 0.006

        while done[0] != 0:
            server.wait()

        root = server.ctrl.display.get("tasks", "roottask")
        cns  = server.ctrl.display.get('ramp', 'consensus')
        assert root in cns
        assert len(cns[root])
        server.change(DpxRamp, 'displaytype', 1, rendered = True)
        server.change(DpxRamp, 'displaytype', 2, rendered = True)

        for slider in server.doc.select({'type': Slider}):
            server.change(slider, 'value', slider.start)
            server.change(slider, 'value', slider.end)
            server.change(slider, 'value', (slider.start + slider.end)*.5)

if __name__ == '__main__':
    test_rampview(bokehaction(None))
