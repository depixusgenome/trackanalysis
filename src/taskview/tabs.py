#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all view aspects here"
from typing              import ClassVar, Tuple

from view.tabs           import ( # pylint: disable=unused-import
    TabsTheme,
    TThemeType,
    TabsView as _TView,
    initsubclass as _init
)

class TabsView(_TView[TThemeType]):
    "A view with all plots"
    TASKS_CLASSES : ClassVar[Tuple[type]]
    TASKS         : ClassVar[Tuple[type]]

    def ismain(self, ctrl):
        "Allows setting-up stuff only when the view is the main one"
        for i in self.TASKS_CLASSES:
            print(i, self.__select(i))
            self.__select(i).ismain(ctrl)
        print("------------>", self, self.TASKS)
        ctrl.theme.updatedefaults("tasks.io", tasks = self.TASKS)
        super().ismain(ctrl)

    @staticmethod
    def _addtodoc_oneshot() -> Tuple[str, str]:
        return "tasks", "opentrack"

def initsubclass(name, keys, tasksclasses = ()):
    "init TabsView subclass"
    _super = _init(name, keys)
    def _fcn(lst):
        return tuple(j for i, j in enumerate(lst) if j not in lst[:i])
    def _wrapper(cls):
        cls = _super(cls)
        cls.TASKS_CLASSES = tuple(tasksclasses)
        cls.TASKS         = _fcn(sum((list(i.TASKS) for i in cls.TASKS_CLASSES), []))
        return cls
    return _wrapper
