#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Imported by pytest: adds 2 fixtures"
from   pathlib import Path
import warnings
from   importlib import import_module
import pytest
import random

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
from tests.testutils.recording     import (record,
                                           pytest_addoption as _adoption,
                                           pytest_collection_modifyitems as _modifyitems)


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
    if config.getoption("--randomize"):
        # Sort items a second time, now in random order. This way the random test-excecution remains
        # the same for the same seed, even when e.g. the linenumbers change for a test.
        _rand = random.Random()  # create instance to avoid a defined seed everywhere in the program
        _rand.seed(config.inicfg['seed'])
        items.sort(key = lambda x: (_sorter(x)[0], _rand.random()))

    _modifyitems(items, config)

def pytest_addoption(parser):
    parser.addoption("--randomize", action="store_true", default=False,
                     help="Randomize the order of the tests within each test-type.")
    parser.addoption("--seed", action="store", default=None,
                     help="Set the seed for shuffling the test-order.")
    _adoption(parser)

def pytest_configure(config):
    if config.getoption("--randomize"):
        if config.getoption("--seed") is not None:
            if not config.getoption("--randomize"):
                raise ValueError("Must use '--randomize' option when manually setting '--seed'.")
            config.inicfg['seed'] = config.getoption("--seed")
        else:
            config.inicfg['seed'] = random.randint(0, 2**31-1)  # seed ∈ [0, max(int32)]

def pytest_report_header(config):
    if config.getoption("--randomize"):
        return f"Randomizing Test-order using seed : {config.inicfg['seed']}"

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
