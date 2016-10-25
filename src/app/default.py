#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import
u"Updates app manager so as to deal with controlers"
from control.taskcontrol    import TaskControler
from control.globalscontrol import GlobalsControler
from .                      import setup

setup(locals(), defaultcontrols = all)
