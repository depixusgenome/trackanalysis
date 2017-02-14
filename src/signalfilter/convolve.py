#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Convolve with a given kernel"
from   typing       import Callable
from   enum         import Enum
from   scipy.signal import fftconvolve
import numpy as np

class KernelMode(Enum):
    u"Kernel modes"
    normal   = 'normal'
    gaussian = normal
    square   = 'square'

class KernelConvolution:
    u"""
    Applies a kernel convolution to the data.

    Initialization:

    * *mode*: 'gaussian' for now
    * *window*: the *half* size of the smearing kernel
    * *width*: the distribution size of the smearing kernel
    * *oversample*: x-axis oversampling

    Keynames "kernel_"+name are synonims
    """
    def __init__(self, **kwa):
        get = lambda name, dlt: kwa.get("kernel_"+name, kwa.get(name, dlt))

        self.window       = get("window", 4)
        self.width        = get("width",  3)
        self.mode         = KernelMode(get("mode", 'normal'))
        self.range        = get('range', 'same')
        self.oversampling = get("oversampling", 1)

    def __call__(self, **kwa) -> Callable[[np.ndarray], np.ndarray]:
        get    = lambda x: kwa.get(x, getattr(self, x))

        mode   = KernelMode(get("mode"))
        window = get('window')
        osamp  = int(get('oversampling')//2) * 2 + 1
        size   = 2*window*osamp+1

        if mode is KernelMode.normal:
            kern  = np.arange(size, dtype = 'f4') / osamp
            kern  = np.exp(-.5*((kern-window)/ get('width'))**2)
            kern /= kern.sum()

        elif mode is KernelMode.square:
            kern  = np.ones((size,), dtype = 'f4') / size
            kern /= len(kern)

        return lambda x: fftconvolve(x, kern, get('range'))
