#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
from  .display    import Display

# pylint: disable=redefined-builtin,wildcard-import
from  .trackviews import *
from  .tracksdict import *

__all__ = ['Display']
