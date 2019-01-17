#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default configurations for each task
"""
from taskmodel.application  import setupdefaulttask
from .                      import (FitToHairpinTask, FitToReferenceTask,
                                    BeadsByHairpinTask)
setupdefaulttask(FitToHairpinTask)
setupdefaulttask(FitToReferenceTask)
setupdefaulttask(BeadsByHairpinTask)
