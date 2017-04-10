#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Processors implement tasks.
They can store results in a cache specific to them.

Processors' cache are managed in the *cache* module.
"""
from .base      import Processor, processors
from .cache     import Cache
from .runner    import Runner, run
