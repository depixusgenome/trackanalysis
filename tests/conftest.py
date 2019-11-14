#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Imported by pytest: adds 2 fixtures"
from   pathlib import Path
import pytest

pytest.register_assert_rewrite("tests.testconfig")
pytest.register_assert_rewrite("tests.testingcore")

# pylint: disable=wrong-import-position
from tests.testingcore             import utpath         # noqa
from tests.testutils.modulecleanup import modulecleanup  # noqa
from tests.testutils               import needsdisplay   # noqa
from tests.testutils.recording     import record, pytest_addoption  # noqa

def pytest_collection_modifyitems(items):
    "sort tests such that integration tests come last and scripting last of all"
    items.sort(key = lambda x: (
        int(x.name != 'test_hybridstat_view[]')
        + 2*int('integration' not in x.keywords.keys())*2
        + 4*int('scripting' in Path(str(x.fspath)).parts if x.fspath else 0)
    ))

@pytest.fixture(params = [pytest.param("", marks = needsdisplay)])
def bokehaction(monkeypatch):
    """
    Create a BokehAction fixture.
    BokehAction.view is the created view. Any of its protected attribute can
    be accessed directly, for example BokehAction.view._ctrl  can be accessed
    through BokehAction.ctrl.
    """
    from tests.testingcore.bokehtesting import BokehAction
    with BokehAction(monkeypatch) as act:
        yield act

@pytest.fixture(scope="module")
def scriptingcleaner():
    "cleanup everything"
    yield from modulecleanup(pairs = [('ACCEPT_SCRIPTING', True)])

@pytest.fixture(scope="module")
def holoviewingcleaner():
    "cleanup everything"
    yield from modulecleanup(pairs = [('ACCEPT_SCRIPTING', 'jupyter')])
