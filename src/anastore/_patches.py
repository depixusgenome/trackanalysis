#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
This must contain json patches up to the versions number in io.__init__.py
"""

def to_version_0(info):
    u"Example: info is a saved *root* item which should be updated"
    return info

_LOCS = locals()
def run(info, fromv, tov):
    u"updates json to current version"
    for ind in range(fromv+1, tov+1):
        info = _LOCS['to_version_'+str(ind)](info)
    return info
