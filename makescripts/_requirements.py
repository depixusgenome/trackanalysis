#!/usr/bin/env python3
# encoding: utf-8
"Everything related to requirements"
from wafbuilder    import requirements as _REQ
from ._utils       import MODULES, BaseContext

class _Requirements(BaseContext):
    fun = cmd = 'requirements'

def requirements(cnf):
    u"prints requirements"
    MODULES(cnf)
    _REQ.tostream()

__all__ = ['requirements']
