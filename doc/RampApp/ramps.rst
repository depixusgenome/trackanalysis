.. include:: ../utils.rst

================
Looking at Ramps
================


The |RampApp| application has two goals:

#. It should allow the user to quickly judge the quality of a field of view.
#. It should tell the user which force to use for that field of view.

This is not for *offline* analysis. This is for to be used with ramp data prior
to testing oligos or antibodies.

Nonetheless, it's possible to export the ramp data in xlsx or csv.

The Ramps Tab
=============

The tab contains:

#. filters for selecting beads as ok, bad or fixed:

    #. |NOISE| allows setting thresholds on the amount of noise a bead is
       allowed to have. Too little means the bead doesn't move which is
       unphysical for a true hairpin. Too much is unusable in further analyses.

    #. |DZ| allows setting thresholds on the size of *ok* beads. This strictly
       dependant on the sequences the user is expecting to see in his field
       of view.
    #. :math:`\Delta z \mathrm{fixed}` is the maximum size a bead may have if
       it is to be considered fixed.

#. A choice of plots:

   #. `raw data` displays cycles one on top of the other. The only doctoring
      performed is to subtract the initial |z| value from each cycle. Colors
      vary depending on the phase of the of the data point. As there
      basically are only two phases for which *zmag* varies, one should see
      two colors.

   #. `Z (% strand size)` displays the average behaviour for a bead (in blue)
      versus that of all *ok* beads (gray). See below for how an average
      behaviour is computed. With this choice of settings, the consensus
      behaviour is computed after normalizing each *ok* bead's height to 100.
      Using this plot allows predicting the percentage of height which will be
      available for analysis at a given force.

   #. `Z (µm)` displays the average behaviour for a bead (in blue)
      versus that of all *ok* beads (gray). See below for how an average
      behaviour is computed. With this choice of settings, the consensus
      behaviour is computed *without* normalizing each *ok* bead's height.
      Using this plot allows seeing the number of bases which will be available
      for analysis at a given force.

#. The number of beads per category:

    #. *ok* are beads which don't raise any flags,
    #. *fixed* are beads which:

        * have a good |NOISE| level,
        * are small enough,
        * and for which a opening jump is detected in phase 2.

    #. *bad* are beads with incorrect |NOISE| or |DZ|.

#. The size of *ok* beads. This size is simply a median of phase 3 minus the
   median of phase 1. These sizes are roughly clustered into bins of a given
   size, which can be set by using the slider. The non-empty bins are reported.

#. The second slider reports the average height of beads at a given force. This
   is the amount of material which will not be measurable because the force
   does not allow the bead to close.

#. Finally the last table reports the average height of beads for a few select
   forces.  

Average Behaviours
==================

The consensus behavior for a bead or a group of bead is performed the same way:

#. For all cycles in turn and at all possible force values, |z| values from phase 4
   and 5 are subtracted from phase 1 and 2. This leaves us with the single
   strand height at a given force.
#. A a given force, aggregating on all cycles, the |z| for the 1st, 2nd and 3rd
   quartile are extracted. These measures provide us with the area shown in
   blue or gray. For the latter, the aggregation is over all cycles from all
   *ok* beads.
