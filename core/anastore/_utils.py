#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for io"

CNT   = '∈'
TPE   = '≡'
STATE = 'ş'
STAR  = '∋'
_LST  = frozenset((bool, str, int, float, type(None)))
def isjsonable(item)-> bool:
    u"Wether this item can be json'ed without conversion"
    # pylint: disable=unidiomatic-typecheck
    tpe = type(item)
    if tpe is list:
        return all(type(i) in _LST for i in item)
    if tpe is dict:
        return all(type(i) in _LST and type(j) in _LST for i, j in item.items())

    return tpe in _LST
