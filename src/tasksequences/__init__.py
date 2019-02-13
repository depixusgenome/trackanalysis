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
