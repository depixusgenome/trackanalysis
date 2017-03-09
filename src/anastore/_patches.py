#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Patch mechanism
"""
from typing import Callable, List # pylint: disable=unused-import
class Patches:
    u"This must contain json patches up to the app's versions number"
    def __init__(self):
        self._patches = [] # type: List[Callable]

    def patch(self, fcn: Callable):
        u"registers a patch"
        self._patches.append(fcn)

    @property
    def version(self):
        u"The current version: this is independant of the git tag"
        return len(self._patches)

    def dumps(self, info):
        u"adds the version to json"
        return [{'version': self.version}, info]

    def loads(self, info):
        u"updates json to current version"
        vers = info[0]['version']+1
        if len(self._patches) < vers:
            return info[1]

        data = info[1]
        for fcn in self._patches[vers:]:
            data = fcn(data)
        return data
