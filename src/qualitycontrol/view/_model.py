#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from   typing               import List, Dict, Set
import numpy                as     np

from   data                 import BEADKEY
from   control.modelaccess  import TaskPlotModelAccess, TaskAccess
from   cleaning.processor   import DataCleaningTask, DataCleaningProcessor

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    @classmethod
    def compute(cls, frame, info, cache = None, **cnf):
        "returns the result of the beadselection"
        err = super().compute(frame, info, cache = cache, **cnf)
        if err:
            cache.setdefault('messages', []).extend([(info[0],)+ i for i in err.args[0].data()])
        return None

class QualityControlModelAccess(TaskPlotModelAccess):
    "access to data cleaning"
    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        self.cleaning   = TaskAccess(self, DataCleaningTask)
        self.config.root.fixedbead.minextent.default = 0.2
        self.__messages = self.project.messages
        self.__messages.setdefault(None)

    def buildmessages(self):
        "creates beads and warnings where applicable"
        default = dict.fromkeys(('type', 'message', 'bead', 'cycles'), []) # type: Dict[str, List]
        tsk     = self.cleaning.task
        if tsk is not None:
            ctx = self.runcontext(GuiDataCleaningProcessor)
            with ctx as view:
                if view is not None:
                    for _ in view:
                        pass

                mem = ctx.taskcache(tsk).pop('messages', None)
                if mem:
                    default = dict(bead    = [i[0] for i in mem],
                                   cycles  = [i[1] for i in mem],
                                   type    = [i[2] for i in mem],
                                   message = [i[3] for i in mem])
        self.__messages.set(default)

    def badbeads(self) -> Set[BEADKEY]:
        "returns bead ids with messages"
        if self.track is None:
            return set()
        return set(self.messages()['bead'])

    def fixedbeads(self) -> Set[BEADKEY]:
        "returns bead ids with extent == all cycles"
        cache   = self.cleaning.cache() # pylint: disable=not-callable
        if cache is None:
            return set()

        minext  = self.config.root.fixedbead.minextent.get()
        def _compute(itm):
            arr   = next((i.values for i in itm if i.name == 'extent'), None)
            if arr is None:
                return False

            valid = np.isfinite(arr)
            return np.sum(arr[valid] < minext) == np.sum(valid)

        return set(i for i, (j, _) in cache.items() if _compute(j))

    def messages(self) -> Dict[str, List]:
        "returns beads and warnings where applicable"
        msg = self.__messages.get()
        if msg is None:
            self.buildmessages()
        return self.__messages.get()

    def clear(self):
        "clears the model's cache"
        self.__messages.pop()
