#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with global information"
from . import View

class GlobalsView(View):
    u"View listing all global info"
    def __init__(self, ctrl = None, **kwa):
        super().__init__(ctrl = ctrl, **kwa)
        self.__ontask(ctrl)
        self.__onstartstop(ctrl)

    @staticmethod
    def __ontask(ctrl):
        cnf          = ctrl.globals.project
        cnf.defaults = dict.fromkeys(('track', 'task', 'bead'), None)

        # pylint: disable=unused-variable
        def _onCloseTrack(model = None, **_):
            tasks: tuple = ('track',)
            if cnf.track.value is model[0]:
                tasks += ('task',)

            inst = next(ctrl.tasks.tasklist(...), None)
            if inst is not None:
                inst = next(iter(inst), None)

            if inst is None:
                del cnf[tasks]
            else:
                cnf.items = {i: inst for i in tasks}

        def _onOpenTrack(model = None, **_):
            cnf.items = {'track': model[0], 'task': model[0], 'bead': None}

        def _onAddTask(parent = None, task = None, **_):
            cnf.items = {'track': parent, 'task' : task}

        def _onUpdateTask(parent = None, task = None, **_):
            cnf.items = {'track': parent, 'task' : task}

        def _onDeleteTask(parent = None, **_):
            cnf.items = {'track': parent, 'task' : parent}

        ctrl.observe([fcn for name, fcn in locals().items() if name[:3] == '_on'])

    @staticmethod
    def __onstartstop(ctrl):
        u"Returns the methods for observing user start & stop action delimiters"
        # pylint: disable=unused-variable
        counts = [False]
        @ctrl.observe
        def _onstartaction(recursive = None):
            if recursive is False:
                counts[0]  = False

        @ctrl.observe(r"^globals\.(?!.*?project).*$")
        def _onconfig(*_):
            counts[0] = True

        if hasattr(ctrl, 'writeuserconfig'):
            @ctrl.observe
            def _onstopaction(recursive = None, **_):
                if recursive is False:
                    if counts[0]:
                        counts[0] = False
                        ctrl.writeuserconfig()
