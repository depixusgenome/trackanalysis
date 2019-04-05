#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Testing anastore"
from   typing           import cast
import warnings

from   tests.testingcore  import path as _utpath, Path
import taskstore

def test_file():
    "tests a ana file"
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category = DeprecationWarning,
                                message  = '.*the imp module is .*')
        for i in Path(cast(str, _utpath())).glob("*.ana"):
            assert taskstore.load(i) is not None
        assert taskstore.load(_utpath("reportv2.xlsx"), fromxlsx = True) is not None

if __name__ == '__main__':
    test_file()
