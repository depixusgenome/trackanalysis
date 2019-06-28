#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All sequences-related stuff"
from    enum        import Enum
from    pathlib     import Path
from    typing      import (Sequence, Union, Iterator, Tuple, TextIO, Dict,
                            List, Iterable, cast)
import  re
import  numpy       as np
from    sequences   import (
    read, PEAKS_DTYPE, PEAKS_TYPE, Translator, peaks, splitoligos,
    marksequence, markedoligos, overlap, Strand
)

class StretchFactor(Enum):
    """
    The stretch factor: bases per µm
    """
    DNA = 1/8.8e-4  # agreed-upon value!
    RNA = 1/7e-4    # invented value!

class StretchRange(Enum):
    """
    The stretch range around the stretch factor: bases per µm
    """
    DNA = 200 # agreed-upon value!
    RNA = 500 # invented value!
