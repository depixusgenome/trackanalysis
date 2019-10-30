#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all cleaning related tasks"
from ._clipping         import ClippingTask, ClippingProcessor
from ._datacleaning     import (DataCleaningTask, DataCleaningException,
                                DataCleaningProcessor, DataCleaningErrorMessage)
from ._beadsubtraction  import (
    BeadSubtractionTask, BeadSubtractionProcessor,
    FixedBeadDetectionTask, FixedBeadDetectionProcessor
)
from ._dataframe        import CleaningDataFrameFactory
from .._core            import Partial  # pylint: disable=import-error
