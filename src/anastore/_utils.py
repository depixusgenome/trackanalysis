#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for io"

def isjsonable(item)-> bool:
    u"Wether this item can be json'ed without conversion"
    tpe = type(item)
    lst = str, int, float
    if tpe in (list, tuple):
        # pylint: disable=unidiomatic-typecheck
        return all(type(i) in lst for i in item)
    if tpe is dict:
        # pylint: disable=unidiomatic-typecheck
        return all(type(i) in lst and type(j) in lst for i, j in item.items())

    return tpe in lst

