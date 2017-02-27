#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates the summary sheet
"""
from typing                 import Optional
import numpy as np

import version

from excelreports.creation  import column_method, sheet_class
from ._base                 import Bead, Reporter

@sheet_class(u"Summary")
class SummarySheet(Reporter):
    u"creates the summary sheet"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def tablerow():
        u"start row of the table"
        return 6

    @staticmethod
    def chartheight(bead:Bead) -> int:
        u"Returns the chart height"
        return 1

    @column_method(u"Newly Clustered", exclude = Reporter.nohairpin)
    def _identified(self, _, bead:Bead) -> bool:
        u"""
        Whether the bead was clustered now or whether its reference comes from
        a previous report
        """
        return not any(bead.key.bead in ref.beads for ref in self.hpins)

    @staticmethod
    @column_method(u"Signal Noise", units = u'µm')
    def _uncert(_, bead:Bead) -> float:
        u"""
        Standard deviation of the signal in events after drift removal.
        """
        return bead.uncertainty

    @staticmethod
    @column_method(u"Silhouette", cond = dict(type = 'data_bar'))
    def _silh(_, bead:Bead) -> float:
        u"""
        Silhouette of the bead: cluster quality factor.
        Values range from -1 (bad) to 1. (good).

        The formula is:
            - a = distance to the current cluster's reference bead
            - b = minimum distance to other reference beads
            => silhouette = 2.*(b-a)/max(a,b)-1.
        """
        return bead.silhouette

    @staticmethod
    @column_method(u"Distance")
    def _dist(_, bead:Bead) -> float:
        u"""
        distance to group's central bead:
        how likely this beads belongs to the group
        """
        return 0. if bead is None else bead.distance.value

    @staticmethod
    @column_method(u"Cycle Count")
    def _ccount(_, bead:Bead) -> Optional[int]:
        u"Number of good cycles for this bead"
        return None if bead is None else bead.ncycles

    @staticmethod
    @column_method(u"Stretch",
                   units = lambda x: None if x.nohairpin() else u'base/µm')
    def _stretch(_, bead:Bead) -> Optional[float]:
        u"""
        Parameter B in the formula "x_central = A*x_bead+B"
        converting this bead's peak position axis to
        the central bead's.
        """
        return None if bead is None else bead.distance.stretch

    @staticmethod
    @column_method(u"Bias", units = Reporter.baseunits)
    def _bias(_, bead:Bead) -> Optional[float]:
        u"""
        Parameter A in the formula "x_central = A*x_bead+B"
        converting this bead's peak position axis to
        the central bead's.
        """
        return None if bead is None else bead.distance.bias

    @column_method(u"Chi²")
    def _chi2(self, _, bead:Bead) -> Optional[float]:
        u"How linear the relationship between peaks is."
        if bead is None:
            return None

        dist  = bead.distance
        good  = np.isfinite(bead.peaks[:,1])
        chi2  = (bead.peaks[good,0]*dist.stretch+dist.bias-bead.peaks[good,1])**2
        count = good.sum()
        if count > 0:
            return chi2/(count*((dist.stretch*self.uncertainty(bead))**2))
        else:
            return None

    @staticmethod
    @column_method(u"Peak Count")
    def _npeaks(_, bead:Bead) -> Optional[int]:
        u""" Number of peaks detected for that bead."""
        return len(bead.peaks)

    @staticmethod
    @column_method(u"Unidentified Peak Count", exclude = Reporter.nohairpin)
    def _unidentifiedpeaks(_, bead:Bead) -> Optional[int]:
        u"""
        Number of peaks detected for that bead
        that were not found in the reference.
        """
        # ignore first peak which is always set to zero in the ref
        return np.isnan(bead.peaks[1:,1]).sum()

    @column_method(u"", exclude = lambda x: not x.isxlsx())
    def _chart(self, *args):
        return self.charting(*args)

    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"
        for group in self.groups:
            yield (group, None)
            yield from ((group, bead) for bead in group.beads)

    def info(self, cnf = ''):
        u"create header"
        sigmas = self.uncertainties()
        # pylint: disable=no-member
        items  = [("GIT Version:",  version.version()),
                  ("GIT Hash:",     version.lasthash()),
                  ("GIT Date:",     version.hashdate()),
                  ("Config:",       cnf),
                  ("Median Noise:", np.median(sigmas))
                 ]
        if len(self.oligos) > 0:
            items.append(("Oligos:", ','.join(self.oligos)))
        self.header(items)
