#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"utils for inspecting objects and frames"
from   typing      import Dict, Any
from   collections import ChainMap
from   .inspection import diffobj


class ConfigObject:
    """
    Object with a few helper function for comparison
    """
    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def diff(self, other) -> Dict[str, Any]:
        "return the diff with `other`"
        return diffobj(self, other)

    def config(self, tpe = dict):
        "return a chainmap with default and updated values"
        if tpe in (dict, 'dict'):
            return dict(self.__dict__)

        get  = lambda i: getattr(i, '__dict__', i)
        cur  = {i: get(j)                          for i, j in self.__dict__.items()}
        dflt = {i: get(getattr(self.__class__, i)) for i in self.__dict__}
        return ChainMap({i: j for i, j in cur.items() if j != dflt[i]}, dflt)


def bind(ctrl, master, slave):
    """
    bind to main tasks model
    """
    if isinstance(master, str):
        master = ctrl.model(master)

    if isinstance(slave, str):
        slave = ctrl.model(slave)

    if master is not slave:
        ctrl.observe(master, lambda **_: ctrl.update(slave, **slave.diff(master)))
