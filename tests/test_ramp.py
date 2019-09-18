#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"tests opening, reading and analysis of a ramp.trk file"
from   bokeh.models               import Tabs
import selenium.common.exceptions
from taskcontrol.taskcontrol    import create
from taskmodel                  import TrackReaderTask
from ramp.processor             import RampStatsTask, RampEventTuple, RampCycleTuple
from ramp.view._widget          import DpxRamp, Slider # pylint: disable=protected-access
from tests.testutils            import integrationmark
from tests.testingcore          import path

FILTERS = [
    (FutureWarning,      ".*elementwise comparison failed;.*"),
    (RuntimeWarning,     ".*All-NaN slice encountered.*"),
    (DeprecationWarning, ".*elementwise comparison failed;.*"),
    (DeprecationWarning, '.*Using or importing the ABCs from.*'),
    (DeprecationWarning, '.*the html argument of XMLParser.*'),
]

def test_dataframe():
    "test ramp dataframe"
    add = {'fixed', 'status', 'good', 'track', 'modification'}
    out = next(create(
        TrackReaderTask(path = path("ramp_legacy")),
        RampStatsTask()
    ).run())
    assert set(out.columns)  == set(RampCycleTuple.fields()) | add

    out = next(create(
        TrackReaderTask(path = path("ramp_legacy")),
        RampStatsTask(events = True)
    ).run())
    assert set(out.columns)  == set(RampEventTuple.fields()) | add

    out = next(create(
        TrackReaderTask(path = path("ramp_Hela_mRNA_CIP_4ul_F9.trk")),
        RampStatsTask()
    ).run())
    assert set(out.columns)  == set(RampCycleTuple.fields()) | add

    status  = out.reset_index().groupby("status").bead.unique()
    assert sorted(status.loc['ok'])    == [1, 2, 3, 4, 7,  8, 9, 11, 12]
    assert sorted(status.loc['fixed']) == [0, 5, 10, 13]
    assert sorted(status.loc['bad'])   == [6]

@integrationmark
def test_rampview(bokehaction): # pylint: disable=redefined-outer-name
    "test the view"
    done = [0]
    def _ondone(start = None, **_):
        if start:
            done[0] += 1
        else:
            done[0] -= 1
    server = bokehaction.start('ramp.view.RampPlotView', 'taskapp.toolbar', filters = FILTERS)
    server.ctrl.display.observe("ramp.pool", _ondone)
    server.load('ramp_5HPs_mix.trk')
    server.change(server.widget.get('Main:toolbar'), 'bead', 2, rendered = True)

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

@integrationmark
def test_cleaningview(bokehaction): # pylint: disable=redefined-outer-name
    "test changing extensions in ramps or cleaning"
    server = bokehaction.start(
        'ramp.view.RampView', 'taskapp.toolbar',
        filters = FILTERS,
        runtime = "selenium",
    )
    tabs = next(iter(server.doc.select({'type': Tabs})))
    try:
        server.selenium[".dpx-modal-done"].click()
    except selenium.common.exceptions.NoSuchElementException:
        pass

    server.load('ramp_5HPs_mix.trk')
    server.change(server.widget.get('Main:toolbar'), 'bead', 2, rendered = True)

    get   = lambda x: server.selenium[
        "#dpx-rp-maxextension" if x else "#dpx-cl-maxextent"
    ].get_attribute("value")
    xinit = get(True)

    server.change(tabs, 'active', 1, rendered = True)
    assert get(False) == xinit
    server.change('Cleaning:Filter', 'maxextent', float(xinit)+1)
    assert get(False) == str(float(xinit)+1).replace('.0', '')
    server.wait()

    assert server.ctrl.theme.get("ramp", "dataframe").extension[2] == float(xinit)+1
    server.change(tabs, 'active', 2, rendered = True)
    assert get(True) == str(float(xinit)+1).replace('.0', '')
    server.change('Ramp:Filter', 'maxextension', float(xinit))
    assert get(True) == xinit

    server.change(tabs, 'active', 1, rendered = True)
    assert get(False) == xinit

if __name__ == '__main__':
    from tests.testingcore.bokehtesting import BokehAction
    with BokehAction(None) as bka:
        test_cleaningview(bka)
