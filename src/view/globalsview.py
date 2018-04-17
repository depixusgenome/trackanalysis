#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with global information"
from . import View

class GlobalsView(View):
    u"View listing all global info"
    def __init__(self, ctrl = None, **kwa):
        super().__init__(ctrl = ctrl, **kwa)

    def observe(self, ctrl):
        "observing the controller"
        cnf          = ctrl.globals.project
        cnf.defaults = dict.fromkeys(('track', 'bead'), None)

        # pylint: disable=unused-variable
        def _onCloseTrack(**_):
            tasks: tuple = ('track',)
            inst = next(ctrl.tasks.tasklist(...), None)
            if inst is not None:
                inst = next(iter(inst), None)

            if inst is None:
                del cnf[tasks]
            else:
                cnf.items = {i: inst for i in tasks}

        def _onOpenTrack(model = None, **_):
            cnf.items = {'track': model[0], 'bead': None}

        ctrl.observe([fcn for name, fcn in locals().items() if name[:3] == '_on'])
