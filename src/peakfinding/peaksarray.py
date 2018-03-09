#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Types used by this module"
from typing import Iterable, Tuple, Union, Sequence
import numpy as np

from utils  import EVENTS_TYPE, EVENTS_DTYPE, EventsArray # pylint: disable=unused-import

EventsOutput        = Sequence[Sequence[EVENTS_TYPE]]
Input               = Union[Iterable[Iterable[np.ndarray]], Sequence[EVENTS_TYPE]]
Output              = Tuple[float, EventsOutput]

class PeaksArray(EventsArray):
    """Array with metadata."""
    _discarded = 0      # type: ignore
    _dtype     = None
