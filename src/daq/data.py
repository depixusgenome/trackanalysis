#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The database
"""
from   typing  import Iterable, Tuple
import numpy   as     np
from   .model  import DAQClient

class RoundRobinVector:
    """
    vector for speeding outputs
    """
    _BUFFERSIZE = 3
    def __init__(self, maxlength:int, columns: np.dtype) -> None:
        self._array  = np.ndarray(maxlength*self._BUFFERSIZE, dtype = columns)
        self._index  = slice(0, 0)
        self._length = self._array.size//self._BUFFERSIZE

    def view(self, name = None) -> np.ndarray: # pylint: disable=arguments-differ
        """
        return the current data
        """
        return (self._array if name is None else self._array[name])[self._index]

    def getnextlines(self, count) -> Tuple[np.ndarray, slice]:
        """
        add values to the end of the table
        """
        ind = slice(self._index.stop, self._index.stop+count)
        if ind.stop > len(self._array):
            self._index              = slice(0, self._length-count)
            self._array[self._index] = self._array[count-self._length:]
            ind                      = slice(self._index.stop, self._length)

        return self._array[ind], slice(max(ind.stop - self._length, 0), ind.stop)

    def applynextlines(self, ind):
        """
        add values to the end of the table
        """
        self._index = ind

    def append(self, lines):
        """
        add values to the end of the table
        """
        arr, ind = self.getnextlines(len(lines))
        arr[:]   = lines
        self.applynextlines(ind)

    def reconfigure(self, maxlength: int, *args):
        "sets a new max length"
        # pylint: disable=no-value-for-parameter
        samedata = self.fulltype(*args) == self._array.dtype
        if self._length == maxlength and samedata:
            return self

        copy = self.__class__(maxlength, *args)
        if samedata:
            copy.append(self.view()[:maxlength])
        return copy

    @property
    def basetype(self) -> np.dtype:
        "return the dtype"
        return self._array.dtype

    @property
    def maxlength(self) -> int:
        "return the max length of the arra"
        return self._length

    @staticmethod
    def fulltype(columns, *_):
        "return the full type of the array (used by child classes)"
        return columns

    def clear(self):
        "removes all data"
        self._index = (0, 0)

class FoVRoundRobinVector(RoundRobinVector):
    """
    Deals with fov data
    """
    def __init__(self, maxlength:int, offset:int, columns: np.dtype, bytesize:int) -> None:
        super().__init__(maxlength, self.fulltype(offset, columns, bytesize))
    setup = __init__

    @staticmethod
    def fulltype(offset:    int,    # type: ignore # pylint: disable=arguments-differ
                 columns:   np.dtype,
                 bytesize:  int,
                 *_) -> np.dtype:
        "create the dtype for all beads"
        return DAQClient(offset = offset, columns = columns, bytesize = bytesize).fovtype()

    @property
    def basetype(self):
        "create the basic dtype for the fov"
        left = size = 0
        for left, name in enumerate(self._array.dtype.names):
            if name[:2] != 'l_':
                break

        for size, name in enumerate(self._array.dtype.names[left:]):
            if name[:2] == 'r_':
                break

        return np.dtype(self._array.dtype.descr[left:size+left])

    @classmethod
    def create(cls, config, maxlen) -> 'FoVRoundRobinVector':
        "create an instance"
        fov = getattr(getattr(config, 'network', config), 'fov', config)
        return cls(maxlen, fov.offset, fov.columns, fov.bytesize)

class BeadsRoundRobinVector(RoundRobinVector):
    """
    Deals with bead data
    """
    def __init__(self, maxlength:int, nbeads:int, columns: np.dtype) -> None:
        super().__init__(maxlength, self.fulltype(nbeads, columns))
        self._ncols    = len(columns.names)
        self._basetype = columns
        self._nbeads   = nbeads
    setup = __init__

    @staticmethod
    def fulltype(nbeads:int,    # type: ignore # pylint: disable=arguments-differ
                 columns: np.dtype,
                 *_):
        "create the dtype for all beads"
        return DAQClient(offset = 0, columns = columns).beadstype(nbeads)

    @property
    def basetype(self):
        "create the dtype for all beads"
        return self._basetype

    def removebeads(self, indexes: Iterable[int]):
        "removes some beads"
        indexes = {i for i in indexes if i < self._nbeads}
        if len(indexes) == 0:
            return

        old = self._array
        self.setup(self._length, self._nbeads - len(indexes), self.basetype)

        names = [old.dtype.names[0],
                 *(i for i in old.dtype.names[1:] if int(i[1:]) not in indexes)]
        assert len(names) == len(self._array.dtype.names)
        for i, j in zip(self._array.dtype.names, names):
            self._array[i] = old[j]

    @property
    def nbeads(self) -> int:
        "return the number of beads"
        return self._nbeads

    @nbeads.setter
    def nbeads(self, nbeads: int):
        "removes or adds beads"
        if nbeads == self._nbeads:
            return

        old = self._array
        self.setup(self._length, nbeads, self.basetype)
        names = (old if old.dtype.itemsize < self._array.dtype.itemsize else
                 self._array).dtype.names
        for i in names:
            self._array[i] = old[i]

    @classmethod
    def create(cls, config, maxlen) -> 'BeadsRoundRobinVector':
        "create an instance"
        return cls(maxlen, len(config.beads), config.network.beads.columns)

class DAQData:
    """
    All information related to the DAQ
    """
    def __init__(self, config, fovmaxlen  = 10000, beadsmaxlen = 10000):
        self.fov          = FoVRoundRobinVector  .create(config, fovmaxlen)
        self.beads        = BeadsRoundRobinVector.create(config, beadsmaxlen)
        self.fovstarted   = False
        self.beadsstarted = False

    def clear(self, name = ...):
        "remove all data"
        assert name in ('beads', 'fov', ...)
        if name in (..., 'beads'):
            self.beads.clear()

        if name in (..., 'fov'):
            self.fov.clear()
