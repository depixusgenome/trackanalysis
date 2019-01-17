#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Deals with undos'
from control.event  import Controller, NoEmission
from .model         import UndoModel

class UndoController(Controller):
    'View listing all undos'
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__isundoing = False
        self.__model     = kwa.get('undos', UndoModel())

    def __apply(self):
        items = self.__model.pop(self.__isundoing)
        if len(items) > 0:
            for fcn in items:
                fcn()

    @Controller.emit
    def clearundos(self) -> None:
        'Removes the controller'
        self.__model.clear()

    @Controller.emit
    def appendundos(self, lst) -> dict:
        'Adds to the undos'
        if len(lst):
            self.__model.append(self.__isundoing, lst)
            self.__isundoing = False
            return dict(items = lst)
        raise NoEmission("empty undo list")

    @Controller.emit
    def undo(self) -> None:
        'undoes one action'
        self.__isundoing = True
        self.__apply()

    @Controller.emit
    def redo(self) -> None:
        'redoes one action'
        self.__apply()
