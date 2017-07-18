#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"remove warnings"
import sys
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category = DeprecationWarning)
    warnings.filterwarnings('ignore', category = FutureWarning)
    try:
        import pandas.tslib # pylint: disable=unused-import
    except ImportError:
        pass
try:
    import bkcharts
    sys.modules['bokeh.charts'] = bkcharts
except ImportError:
    pass
warnings.filterwarnings('ignore',
                        category = DeprecationWarning,
                        message  = '.*elementwise == comparison failed.*')
warnings.filterwarnings('ignore',
                        category = DeprecationWarning,
                        message  = '.* deprecated in Bokeh 0.12.6 .*')
