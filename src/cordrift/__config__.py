#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default configurations for each task
"""
from taskmodel.application  import setupdefaulttask
from .processor             import DriftTask

setupdefaulttask(DriftTask, 'driftperbead',  onbeads = True)
setupdefaulttask(DriftTask, 'driftpercycle', onbeads = False)
