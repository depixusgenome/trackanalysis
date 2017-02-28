#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for io"

CNT  = '∈'
TPE  = '≡'
_LST = frozenset((bool, str, int, float, type(None)))
def isjsonable(item)-> bool:
    u"Wether this item can be json'ed without conversion"
    tpe = type(item)
    if tpe is list:
        # pylint: disable=unidiomatic-typecheck
        return all(type(i) in _LST for i in item)
    if tpe is dict:
        # pylint: disable=unidiomatic-typecheck
        return all(type(i) in _LST and type(j) in _LST for i, j in item.items())

    return tpe in _LST
