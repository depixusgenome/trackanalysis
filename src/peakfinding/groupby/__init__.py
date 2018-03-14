#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'initializer for expectation maximization'
from typing import Union

from .._core          import exppdf, normpdf # pylint:disable=import-error
from .emfitter        import ByEM, ByEmMutu
from .gaussianfitter  import ByGaussianMix
from .histogramfitter import (ZeroCrossingPeakFinder,
                              SubPixelPeakPosition,
                              ByHistogram,
                              CWTPeakFinder)


PeakFinder= Union[ByHistogram,ByGaussianMix,ByEM]
