#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Imported by pytest: adds 2 fixtures"
from   pathlib import Path
import warnings
from   importlib import import_module
import pytest

with warnings.catch_warnings():
    # for _msg_ in (".*html argument of XMLParser.*", ".*Using or importing the ABCs.*"):
    warnings.filterwarnings('ignore', category = DeprecationWarning)
    try:
        import_module("defusedxml.lxml")
    except ModuleNotFoundError:
        pass

pytest.register_assert_rewrite("tests.testconfig")
pytest.register_assert_rewrite("tests.testingcore")

# pylint: disable=wrong-import-position
from tests.testingcore             import utpath         # noqa
from tests.testutils.modulecleanup import modulecleanup  # noqa
from tests.testutils               import needsdisplay   # noqa
from tests.testutils.recording     import (
    record, pytest_addoption, pytest_collection_modifyitems as _modifyitems
)

def pytest_collection_modifyitems(items, config):
    "sort tests such that integration tests come last and scripting last of all"
    def _sorter(itm):
        test_type = (int(itm.name != 'test_hybridstat_view[]')
                     + 2*int('integration' not in itm.keywords.keys())
                     + 4*int('scripting' in Path(str(itm.fspath)).parts if itm.fspath else 0))
        filepath = Path(itm.location[0])
        # take filepath relative to second parent if file has at least 2 parents
        if len(filepath.parents) >= 2:
            filepath = filepath.relative_to(filepath.parents[1])
        linenumber = itm.location[1]
        return (test_type, filepath, linenumber)
    items.sort(key = _sorter)
    _modifyitems(items, config)

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
