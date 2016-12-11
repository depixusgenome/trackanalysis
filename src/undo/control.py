#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from control.event import Controller
from .model        import UndoModel

class UndoController(Controller):
    u"View listing all undos"
    def __init__(self, **kwa): # pylint: disable=too-many-locals
        super().__init__(**kwa)
        self.__isundoing = False
        self.__model     = kwa.get('undos', UndoModel())

    def __apply(self):
        items = self.__model.pop(self.__isundoing)
        if len(items) > 0:
            for fcn in items:
                fcn()

    @Controller.emit
    def clearUndos(self) -> None:
        u"Removes the controller"
        self.__model.clear()

    @Controller.emit
    def appendUndos(self, lst) -> dict:
        u"Adds to the undos"
        self.__model.append(self.__isundoing, lst)
        return dict(items = lst)

    @Controller.emit
    def undo(self) -> None:
        u"undoes one action"
        self.__isundoing = True
        try:
            self.__apply()
        finally:
            self.__isundoing = False

    @Controller.emit
    def redo(self) -> None:
        u"redoes one action"
        self.__apply()
