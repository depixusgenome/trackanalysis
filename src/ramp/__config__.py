#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default configurations for each task
"""
from taskmodel.application import setupdefaulttask
from .processor            import RampConsensusBeadTask, RampStatsTask
setupdefaulttask(RampConsensusBeadTask)
setupdefaulttask(RampStatsTask)
