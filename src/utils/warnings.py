#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"remove warnings"
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category = FutureWarning)
    try:
        import pandas.tslib # pylint: disable=unused-import
    except ImportError:
        pass
    warnings.filterwarnings('ignore', category = DeprecationWarning)
    try:
        import bokeh.charts # discard bokeh warning # pylint: disable=unused-import
    except ImportError:
        pass
