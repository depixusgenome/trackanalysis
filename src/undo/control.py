#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Deals with undos'
from typing         import Set, Callable # pylint: disable=unused-import
from control.event  import Controller
from .model         import UndoModel

class UndoController(Controller):
    'View listing all undos'
    __UNDOS = set() # type: Set[Callable]
    def __init__(self, **kwa): # pylint: disable=too-many-locals
        super().__init__(**kwa)
        self.__isundoing = False
        self.__model     = kwa.get('undos', UndoModel())

    @classmethod
    def __undos__(cls):
        yield from cls.__UNDOS

    @classmethod
    def registerundos(cls, *undos):
        'registers new undos'
        cls.__UNDOS |= frozenset(undos)

    def __apply(self):
        items = self.__model.pop(self.__isundoing)
        if len(items) > 0:
            for fcn in items:
                fcn()

    @Controller.emit
    def clearUndos(self) -> None:
        'Removes the controller'
        self.__model.clear()

    @Controller.emit
    def appendUndos(self, lst) -> dict:
        'Adds to the undos'
        self.__model.append(self.__isundoing, lst)
        return dict(items = lst)

    @Controller.emit
    def undo(self) -> None:
        'undoes one action'
        self.__isundoing = True
        try:
            self.__apply()
        finally:
            self.__isundoing = False

    @Controller.emit
    def redo(self) -> None:
        'redoes one action'
        self.__apply()
