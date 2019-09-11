#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Removing aberrant points and cycles"
from    importlib               import import_module
# pylint: disable=import-error
from    ._core                  import DataCleaning   # pylint: disable=unused-import

# next lines are needed to open legacy .pk files...
locals().update({
    i for i in import_module("cleaning._core").__dict__.items()
    if i[0][0].upper() == i[0][0] and i[0][0] != '_'
})
locals()['DerivateIslands'] = locals().pop('NaNDerivateIslands')
