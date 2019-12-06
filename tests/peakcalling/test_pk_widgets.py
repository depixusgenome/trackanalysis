#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"test peakcalling views widgets"
from tests.testutils   import integrationmark
from tests.testingcore import path as utpath
from sequences         import read as _read
from peakcalling.processor import FitToHairpinTask


@integrationmark
def test_diskcache_view(pkviewserver):
    "test the view"
    # reconstructing a new disk cache because selenium can't deal with too big an html file ?
    pkviewserver.CDIR = str(pkviewserver.CDIR)+"_new"
    server, fig = pkviewserver(evt = pkviewserver.EVT)
    size        = len(fig.renderers[0].data_source.data['boxheight'])

    # pylint: disable=protected-access
    cnf = server.view.views[0]._mainview._widgets[0].cache._model.diskcache
    assert cnf.path == server.ctrl.theme.model('peakcalling.diskcache').path

    with server.ctrl.theme.model('peakcalling.diskcache').newcache() as cache:
        for _ in range(5):
            if any(i.startswith(b'data_') for i in cache.iterkeys()):
                break
            server.wait()
        assert any(i.startswith(b'data_') for i in cache.iterkeys())

    modal       = server.selenium.modal("//span[@class='icon-dpx-download2']", True)
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
        assert proc.model[-1].sequences == dict(_read(utpath("hairpins.fasta")))
        assert [i.lower() for i in proc.model[-1].oligos] == ['ctgt']
        assert proc.model[3].events.select.minlength == 10
        assert not any(i.__class__.__name__ == 'ExtremumAlignmentTask' for i in proc.model)

@integrationmark
def test_taskdialog_fit_view(pkviewserver):
    "test the view"
    server = pkviewserver()[0]
    server.ctrl.theme.model("peakcalling.view.stats").linear = False
    server.addhp(sequences = utpath("hp6.fasta"), oligos = ["aacc"], rendered = True)
    assert set(server.task(FitToHairpinTask).sequences) == {'full', 'oligo', 'target'}
    assert server.task(FitToHairpinTask).oligos == ['aacc']
    assert set(server.task(FitToHairpinTask).fit) == {'full', 'oligo', 'target'}

    modal = server.selenium.modal("//span[@class='icon-dpx-cog']", True)
    with modal:
        modal.tab("Hairpins")
        modal[f"//input[@name='items[0].fit.task.sequences']"] = str(utpath("hairpins.fasta"))
        modal.tab("Oligos")
        modal[f"//input[@name='items[0].fit.task.oligos']"] = "kmer"
    server.wait()
    assert set(server.task(FitToHairpinTask).sequences) == {'015', *(f'GF{i}' for i in range(1, 5))}
    assert server.task(FitToHairpinTask).oligos == ['ctgt']
    assert set(server.task(FitToHairpinTask).fit) == {'015', *(f'GF{i}' for i in range(1, 5))}

    with modal:
        assert (
            modal[f"//input[@name='items[0].fit.task.sequences']"].get_attribute('value')
            == str(utpath("hairpins.fasta"))
        )
        assert (
            modal[f"//input[@name='items[0].fit.task.oligos']"].get_attribute('value')
            == "ctgt"
        )


if __name__ == '__main__':
    from pathlib import Path
    # test_statsplot_info_pkcount(Path("/tmp/dd"))
    from importlib import import_module
    from tests.testingcore.bokehtesting import BokehAction
    with BokehAction(None) as bka:
        test_diskcache_view(
            getattr(
                import_module("tests.peakcalling.conftest"), '_server'
            )(bka, Path("/tmp/disk_dir"), "")
        )
