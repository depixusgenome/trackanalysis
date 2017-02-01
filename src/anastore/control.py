#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Sets things up for the taskcontroller"

from control    import FileIO
from .          import load, dump

class AnaIO(FileIO):
    u"Ana IO"
    def open(self, path:str, model:tuple):
        u"opens an ana file"
        out = load(path)
        if out is not None and len(model):
            raise NotImplementedError("Don't know what to do")
        return out

    def save(self, path:str, models):
        u"closes an ana file"
        if not path.endswith(".ana"):
            return False
        dump(models, path)
        return True
