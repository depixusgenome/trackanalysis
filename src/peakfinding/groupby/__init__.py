#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'initializer for expectation maximization'
from typing import Union

from .._core           import exppdf, normpdf
from .emfitter        import ByEM
from .gaussianfitter  import ByGaussianMix
from .histogramfitter import ZeroCrossingPeakFinder, SubPixelPeakPosition, ByHistogram


PeakFinder= Union[ByHistogram,ByGaussianMix,ByEM]
