#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
The database
"""
from   typing  import Iterable
import numpy   as     np

class RoundRobinVector:
    """
    vector for speeding outputs
    """
    _BUFFERSIZE = 3
    def __init__(self, columns: np.dtype, maxlength: int):
        dtype        = [(i, 'f4') for i in columns]
        self._array  = np.ndarray(maxlength*self._BUFFERSIZE, dtype = dtype)
        self._index  = slice(0, 0)
        self._length = self._array.size//self._BUFFERSIZE

    def view(self) -> np.ndarray:
        """
        return the current data
        """
        return self._array[self._index]

    def append(self, lines):
        """
        add values to the end of the table
        """
        ind = slice(self._index.stop, self._index.stop+len(lines))
        if ind.stop > len(self._array):
            self._index              = slice(0, self._length-len(lines))
            self._array[self._index] = self._array[-1-self._index.stop:]
            ind                      = slice(self._index.stop, self._length)

        self._index      = slice(max(ind.stop - self._length, 0), ind.stop)
        self._array[ind] = lines

    def reconfigure(self, columns:np.dtype, maxlength:int):
        "sets a new max length"
        if self._length == maxlength and self._array.dtype.names == columns:
            return self

        copy = self.__class__(columns, maxlength)
        if self._array.dtype.names == columns:
            copy.append(self.view()[:maxlength])
        return copy

    def clear(self):
        "removes all data"
        self._index = (0, 0)

class BeadsRoundRobinVector(RoundRobinVector):
    """
    Deals with bead data
    """
    def __init__(self, nbeads:int, columns: np.dtype, maxlength: int) -> None:
        cols = [('time', 'I8')]
        for i in range(nbeads):
            cols += [(j+str(i), k) for j, k in columns.decr]

        super().__init__(np.dtype(cols), maxlength)
        self._ncols = len(columns.names)
        self._nbeads   = nbeads
    setup = __init__

    def view(self, name = None) -> np.ndarray: # pylint: disable=arguments-differ
        """
        return the current data
        """
        return (self._array if name is None else self._array[name])[self._index]

    def removebeads(self, indexes: Iterable[int]):
        "removes some beads"
        self.nbeads = self._nbeads - len(frozenset(indexes))

    @property
    def nbeads(self) -> int:
        "return the number of beads"
        return self._nbeads

    @nbeads.setter
    def nbeads(self, nbeads: int):
        "removes or adds beads"
        if nbeads != self._nbeads:
            cols = np.dtype(self._array.dtype.descr[1:self._ncols+1])
            self.setup(nbeads, np.dtype(cols), self._length)

    @property
    def ncols(self) -> int:
        "return the number of columns per bead"
        return self._ncols

class DAQData:
    """
    All information related to the DAQ
    """
    def __init__(self, config):
        self.fov          = RoundRobinVector(config.fovdata.columns, config.fovdata.maxlength)
        self.beads        = BeadsRoundRobinVector(len(config.beads),
                                                  config.beaddata.columns,
                                                  config.beaddata.maxlength)
        self.fovstarted   = False
        self.beadsstarted = False

    def clear(self, name = ...):
        "remove all data"
        assert name in ('beads', 'fov', ...)
        if name in (..., 'beads'):
            self.beads.clear()

        if name in (..., 'fov'):
            self.fov.clear()
