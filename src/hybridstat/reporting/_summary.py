#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates the summary sheet
"""
from typing                 import Optional
import numpy as np

import version

from excelreports.creation  import column_method, sheet_class
from ._base                 import Bead, Reporter, Group

@sheet_class("Summary")
class SummarySheet(Reporter):
    "creates the summary sheet"
    @staticmethod
    def tablerow():
        "start row of the table"
        return 10

    @staticmethod
    def chartheight(npeaks:int) -> int:
        "Returns the chart height"
        return 1

    @column_method("Newly Clustered", exclude = Reporter.nohairpin)
    def _identified(self, _, bead:Bead) -> bool:
        """
        Whether the bead was clustered now or whether its reference comes from
        a previous report
        """
        return None if bead is None else bead.key not in self.config.knownbeads

    @column_method("Signal Noise", units = 'µm')
    def _uncert(self, _, bead:Bead) -> Optional[float]:
        "Standard deviation of the signal"
        return None if bead is None else self.uncertainty(bead)

    @staticmethod
    @column_method("Silhouette", cond = dict(type = 'data_bar'))
    def _silh(_, bead:Bead) -> float:
        """
        Silhouette of the bead: cluster quality factor.
        Values range from -1 (bad) to 1. (good).

        The formula is:
            - a = distance to the current cluster's reference bead
            - b = minimum distance to other reference beads
            => silhouette = 2.*(b-a)/max(a,b)-1.
        """
        return None if bead is None else bead.silhouette

    @staticmethod
    @column_method("Distance")
    def _dist(_, bead:Bead) -> float:
        """
        distance to group's central bead:
        how likely this beads belongs to the group
        """
        return None if bead is None else bead.distance.value

    @staticmethod
    @column_method("Cycle Count")
    def _ccount(_, bead:Bead) -> Optional[int]:
        "Number of good cycles for this bead"
        return None if bead is None else len(bead.events)

    @staticmethod
    @column_method("Stretch",
                   units = lambda x: None if x.nohairpin() else 'base/µm')
    def _stretch(_, bead:Bead) -> Optional[float]:
        """
        Parameter A in the formula "x_hpin = A*(x_bead-B)"
        converting this bead's peak position axis to
        the hairpin's.
        """
        return None if bead is None else bead.distance.stretch

    @staticmethod
    @column_method("Bias", units = 'µm')
    def _bias(_, bead:Bead) -> Optional[float]:
        """
        Parameter B in the formula "x_hpin = A*(x_bead-B)"
        converting this bead's peak position axis to
        the hairpin's.
        """
        return None if bead is None else bead.distance.bias

    @column_method("Chi²")
    def _chi2(self, _, bead:Bead) -> Optional[float]:
        "How linear the relationship between peaks is."
        if bead is None:
            return None

        good = bead.peaks['key'] >= 0
        if any(good):
            dist = bead.distance
            chi2 = (((bead.peaks['zvalue'][good]-dist.bias)*dist.stretch
                     -bead.peaks['key'][good])**2).mean()
            return chi2/((dist.stretch*self.uncertainty(bead))**2)
        else:
            return None

    @column_method("Peak Count")
    def _npeaks(self, ref:Group, bead:Bead) -> Optional[int]:
        """ Number of peaks detected for that bead."""
        if bead is None:
            return None if ref.key is None else len(self.config.hairpins[ref.key].peaks[:-1])
        return len(bead.peaks)

    @column_method("Unidentified Peak Count", exclude = Reporter.nohairpin)
    def _unidentifiedpeaks(self, ref, bead:Bead) -> Optional[int]:
        """
        For an experimental bead:

            Number of peaks detected for that bead
            that were not found in the reference.

        For a reference:

            Number of peaks never seen
        """
        # ignore first peak which is always set to zero in the ref
        if bead is None:
            if ref.key is None:
                return None

            peaks = self.config.hairpins[ref.key].peaks[1:-1]
            theor = set(np.int32(peaks+.1)) # type: ignore
            for bead in ref.beads:
                theor.difference_update(bead.peaks['key'])
            return len(theor)
        else:
            return (bead.peaks['key'][1:] < 0).sum()

    @column_method("", exclude = lambda x: not x.isxlsx())
    def _chart(self, *args):
        return self.charting(*args)

    def iterate(self):
        "Iterates through sheet's base objects and their hierarchy"
        for group in self.config.groups:
            yield (group, None)
            yield from ((group, bead) for bead in group.beads)

    def info(self, cnf = ''):
        "create header"
        sigmas = self.uncertainties()
        # pylint: disable=no-member
        items  = [("GIT Version:",  version.version()),
                  ("GIT Hash:",     version.lasthash()),
                  ("GIT Date:",     version.hashdate()),
                  ("Config:",       cnf),
                  ("Median Noise:", np.median(sigmas))
                 ]
        if len(self.config.oligos) > 0:
            items.append(("Oligos:", ','.join(self.config.oligos)))
        if isinstance(self.config.track.path, tuple):
            items.append(("Track", str(self.config.track.path[-1])))
        else:
            items.append(("Track", str(self.config.track.path)))
        self.header(items)
