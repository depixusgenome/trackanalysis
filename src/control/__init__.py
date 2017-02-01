#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"controller module"
from .event import Controller

class FileIO:
    u"base class for opening files"
    # pylint: disable=no-self-use,unused-argument
    def open(self, path:str, model:tuple):
        u"opens a file"
        return None

    def save(self, path:str, models):
        u"opens a file"
        return None
