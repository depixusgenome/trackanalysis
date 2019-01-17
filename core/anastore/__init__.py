#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Track Analysis inputs and outputs.

This does not include track files io.
"""
from ._patches  import Patches, modifyclasses, RESET, DELETE
from .api       import dump, dumps, load, loads, isana, version, iterversions, TPE, CNT
