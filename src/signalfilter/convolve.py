#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Convolve with a given kernel"
from   typing       import Callable
from   enum         import Enum
from   scipy.signal import fftconvolve
import numpy as np

from   utils        import initdefaults, kwargsdefaults

class KernelMode(Enum):
    "Kernel modes"
    normal   = 'normal'
    gaussian = normal
    square   = 'square'

class KernelConvolution:
    """
    Applies a kernel convolution to the data.

    Initialization:

    * *mode*: 'gaussian' for now
    * *window*: the *half* size of the smearing kernel
    * *width*: the distribution size of the smearing kernel
    * *oversample*: x-axis oversampling

    Keynames "kernel_"+name are synonyms
    """
    window       = 4
    width        = 1.
    mode         = KernelMode.normal
    range        = 'same'
    oversampling = 1
    @initdefaults(roots = ('', 'kernel'))
    def __init__(self, **_):
        pass

    @kwargsdefaults
    def kernel(self, **_) -> np.ndarray:
        "returns the kernel used for the convolution"
        window = self.window
        osamp  = int(self.oversampling//2) * 2 + 1
        size   = int(2*self.width*window*osamp)+1
        if self.mode is KernelMode.normal:
            kern  = np.arange(size, dtype = 'f4') / osamp
            kern  = np.exp(-.5*((kern-kern[size//2])/ self.width)**2)
            kern /= kern.sum()

        elif self.mode is KernelMode.square:
            kern  = np.ones((size,), dtype = 'f4') / size
            kern /= len(kern)
        return kern

    def __call__(self, **kwa) -> Callable[[np.ndarray], np.ndarray]:
        kern = self.kernel(**kwa)
        rng  = kwa.get('range', self.range)
        return lambda x: np.float32(fftconvolve(x, kern, rng)) # type: ignore
