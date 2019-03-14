#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Imported by pytest: adds 2 fixtures"
import pytest
from tests.testutils.modulecleanup import modulecleanup

@pytest.fixture
def scriptingcleaner():
    "cleanup everything"
    yield from modulecleanup(pairs = [('ACCEPT_SCRIPTING', True)])

@pytest.fixture
def holoviewingcleaner():
    "cleanup everything"
    yield from modulecleanup(pairs = [('ACCEPT_SCRIPTING', 'jupyter')])
