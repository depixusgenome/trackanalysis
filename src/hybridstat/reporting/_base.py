#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines basic hybridstat related report objects and functions
"""
from typing                 import (Tuple, Iterator, Sequence, Optional,
                                    NamedTuple, Callable, Union, cast)
from abc                    import abstractmethod

import numpy as np

from excelreports.creation  import Reporter


Probability = NamedTuple('Probability', [('probability', float),
                                         ('time',        float),
                                         ('uncertainty', float)])
Position    = NamedTuple('Position',    [('x', float), ('y', float), ('completed', bool)])
Events      = Sequence[Position]
Peak        = NamedTuple('Peak', [('pos',    Position),
                                  ('prob',   Optional[Probability]),
                                  ('ref',    Optional[float]),
                                  ('events', Events)])
Peaks       = Sequence[Peak]
Key         = Union[int,str]
Distance    = NamedTuple('Distance', [('val',           float),
                                      ('stretch',       float),
                                      ('bias',          float)])
Bead        = NamedTuple('Bead',     [('key',           Key),
                                      ('ncycles',       int),
                                      ('uncertainty',   float),
                                      ('silhouette',    float),
                                      ('peaks',         Peaks),
                                      ('distance',      Distance)])
Group       = NamedTuple('Group',    [('key',           Key),
                                      ('beads',         Sequence[Bead])])
Groups      = Sequence[Group]
Hairpin     = NamedTuple('Hairpin', [('name', str), ('value', str), ('beads', Sequence[int])])
Hairpins    = Sequence[Hairpin]
Oligos      = Sequence[str]

PULL_PHASE  = 3

def isref(bead:Bead) -> bool:
    u"wether the bead is a hairpin or an experimental bead"
    return isinstance(bead.key, str)

class Base(Reporter):
    u"Basic class for iterating over the data"
    def __init__(self, arg, **kwargs):
        super().__init__(arg)
        if isinstance(arg, Base):
            base        = cast(Base, arg)
            self.groups = base.groups
            self.hpins  = base.hpins
            self.oligos = base.oligos
            self.config = base.config
            self.haslengthpeak = base.haslengthpeak
        else:
            self.groups = kwargs['groups']             # type: Groups
            self.hpins  = kwargs['hairpins']           # type: Hairpins
            self.oligos = kwargs['oligos']             # type: Oligos
            self.config = kwargs['config']             # type: dict
            self.haslengthpeak = self.config['firstphase'] <= PULL_PHASE

    def beads(self) -> Iterator[Tuple[Key,Bead]]:
        u"iterates through groups"
        for k, beads     in self.groups:
            for bead     in beads:
                yield k, bead

    def groupbeads(self, spe = None) -> Iterator[Bead]:
        u"iterates through beads in one group"
        for k, beads     in self.groups:
            if k == spe:
                for bead in beads:
                    if bead.key != spe:
                        yield bead
                break

    def peaks(self, ref:Key, ypos:float) -> Iterator[Tuple[Bead,Peak]]:
        u"iterate over reference peaks in the group"
        for bead in self.groupbeads(ref):
            for peak in bead.peaks:
                if peak.ref is None:
                    continue
                if abs(peak.ref-ypos) < 1.:
                    yield bead, peak

    def baseunits(self)-> str:
        u"Returns the unit value for bases"
        return u"µm" if self.nohairpin() else u"base"

    def basefmt(self)-> type:
        u"Returns the format type for bases"
        return float if self.nohairpin() else int

    def nohairpin(self)-> bool:
        u"returns true if no hairpin was provided"
        return len(self.hpins) == 0

    def uncertainties(self):
        u"returns uncertainties for all beads"
        if len(self.hpins):
            sigmas = iter(bead for ref, bead in self.beads() if ref != bead.key)
            sigmas = iter(bead.uncertainty*bead.distance.stretch for bead in sigmas)
            sigmas = np.fromiter(sigmas, dtype = 'f4')
        else:
            sigmas = np.fromiter((bead.uncertainty for _, bead in self.beads()),
                                 dtype = 'f4')
        return sigmas

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"

def sheettype(name:str):
    u"Returns the columns associated with another sheet"
    for cls in Base.__subclasses__():
        if cls.__name__.lower() in (name.lower(), name.lower()+'sheet'):
            return cls
    raise KeyError('No sheet with name: '+name)

def sheetcolumns(self:Base, name:str):
    u"Returns the columns associated with another sheet"
    return sheettype(name)(self).columns()

class ChartCreator(object):
    u"Creates charts"
    _ERR    = .015
    _WIDTH  = 400
    _HUNIT  = 18
    def __init__(self,
                 parent     : Base,
                 height     : Callable,
                ) -> None:
        peakstype = sheettype('peaks')
        peaks     = parent if isinstance(parent, peakstype) else peakstype(parent)

        self._pos    = tuple(peaks.columnindex(u'Peak Position in Reference',
                                               u'Hybridisation Rate'))
        self._book   = parent.book
        self._height = height
        self._rseries= None      # type: dict
        self._row    = peaks.tablerow()+1

    def _args(self, nrows:int, tpe:str, color:str) -> dict:
        u"return args for creating a chart"
        base   = sheettype('peaks').sheet_name
        def _pos(i):
            return [base, self._row, self._pos[i], self._row+nrows-1, self._pos[i]]
        return dict(name         = [base, self._row, 0],
                    categories   = _pos(0),
                    values       = _pos(1),
                    marker       = dict(type  = tpe,
                                        #size  = 0.1,
                                        fill  = dict(color = color)),
                    x_error_bars = dict(type  = 'fixed',
                                        value = self._ERR,
                                        line  = dict(color = color)))

    def bead(self, ref: Key, bead: Bead):
        u"returns a chart for this bead"
        return self.peaks(ref, bead, bead.peaks[0])

    def peaks(self, ref: Key, bead: Bead, peak: Peak):
        u"returns a chart for this bead if peak is peaks zero"
        if bead.peaks[0] != peak:
            return

        chart = self._book.add_chart(dict(type = 'scatter'))

        if ref != bead.key:
            series = self._args(len(bead.peaks), 'circle', 'green')
            chart.add_series(series)
        else:
            self._rseries = self._args(len(bead.peaks), 'square', 'blue')

        chart.add_series(self._rseries)
        chart.set_title (dict(none  = True))
        chart.set_legend(dict(none  = True))
        axis = dict(major_gridlines = dict(visible = False),
                    label_position  = "none",
                    visible         = True)
        chart.set_x_axis(axis)
        chart.set_y_axis(axis)
        chart.set_size  (dict(width  = self._WIDTH,
                              height = self._HUNIT*self._height(bead)))
        self._row += len(bead.peaks)
        return chart
