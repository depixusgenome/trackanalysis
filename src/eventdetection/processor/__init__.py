#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from ..dataframe     import EventsDataFrameFactory # pylint: disable=unused-import
from .alignment      import AlignmentTactic, ExtremumAlignmentTask, ExtremumAlignmentProcessor
from .biasremoval    import BiasRemovalTask, BiasRemovalProcessor
from .eventdetection import EventDetectionTask, EventDetectionProcessor
