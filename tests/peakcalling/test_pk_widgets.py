#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"test peakcalling views widgets"
from tests.testutils   import integrationmark
from tests.testingcore import path as utpath

@integrationmark
def test_diskcache_view(pkviewserver):
    "test the view"
    server, fig = pkviewserver(evt = True)
    size = len(fig.renderers[0].data_source.data['boxheight'])
    assert size > 0
    if size < 6:
        server.cmd(lambda: None, rendered = pkviewserver.EVT)
        size = len(fig.renderers[0].data_source.data['boxheight'])

    modal = server.selenium.modal("//span[@class='icon-dpx-download2']", True)
    with modal:
        modal["//input[@name='items[0].loaded']"].click()
    server.wait()
    assert len(fig.renderers[0].data_source.data['boxheight']) == 1
    with modal:
        modal["//input[@name='items[0].loaded']"].click()
    server.wait()
    assert len(fig.renderers[0].data_source.data['boxheight']) == size

@integrationmark
def test_taskdialog_view(pkviewserver):
    "test the view"
    server = pkviewserver(evt = True)[0]

    # don't run any computations
    server.ctrl.theme.model("peakcalling.precomputations").ncpu = 0

    modal = server.selenium.modal("//span[@class='icon-dpx-cog']", True)

    for i in server.ctrl.tasks.tasklist(...):
        proc = server.ctrl.tasks.processors(next(i))
        assert proc.model[1].maxextent == 2.
        assert 'fittoh' not in str(proc.model[-1]).lower()

    with modal:
        modal["//input[@name='items[0].sub.task.beads']"] = "31"
        modal.tab("Δz")
        modal["//input[@name='items[0].clean.task.maxextent']"] = "4.0"

    for i in server.ctrl.tasks.tasklist(...):
        proc = server.ctrl.tasks.processors(next(i))
        assert proc.model[1].beads == [31]
        assert proc.model[2].maxextent == 4.

    with modal:
        modal["//input[@name='items[0].sub.task.beads']"] = "31, 38"

    for i in server.ctrl.tasks.tasklist(...):
        proc = server.ctrl.tasks.processors(next(i))
        assert set(proc.model[1].beads) == {31, 38}
        assert proc.model[2].maxextent == 4.

    with modal:
        modal["//input[@name='items[0].sub.task.beads']"] = ""

    for i in server.ctrl.tasks.tasklist(...):
        proc = server.ctrl.tasks.processors(next(i))
        assert proc.model[1].maxextent == 4.
        assert proc.model[4].events.select.minlength != 10
        assert any(i.__class__.__name__ == 'ExtremumAlignmentTask' for i in proc.model)

    with modal:
        modal.tab("Blockage Min Duration")
        modal["//input[@name='items[0].evt.task.events.select.minlength']"] = 10
        modal.tab("Cycle Alignment")
        modal.select("//select[@name='items[0].align.phase']", "0")
        modal.tab("Hairpins")
        modal["//input[@name='items[0].fit.task.sequences']"] = utpath("hairpins.fasta")
        modal.tab("Oligos")
        modal["//input[@name='items[0].fit.task.oligos']"] = "kmer"

    for i in server.ctrl.tasks.tasklist(...):
        proc = server.ctrl.tasks.processors(next(i))
        assert proc.model[-1].sequences == utpath("hairpins.fasta")
        assert [i.lower() for i in proc.model[-1].oligos] == ['ctgt']
        assert proc.model[3].events.select.minlength == 10
        assert not any(i.__class__.__name__ == 'ExtremumAlignmentTask' for i in proc.model)
