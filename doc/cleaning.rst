=============
Data Cleaning
=============

.. figure:: _images/cleaning.png

    The impact of different signal analysis filters on :math:`z` values for a
    given bead. The color blue is used for accepted frames, other colors
    indicate that the frame or even the whole cycle has been discarded.

The goal of this tab is to:

#. define the setting allowing an automated cleaning of all signals. Beads
   failing this automated cleaning are categorized either as *bad* or
   *missing*.
#. define which beads can be considered *fixed*. Such beads are *probably*
   bound non-specifically to the surface and cannot ever open (become
   single-strand). Their behavior is mostly consistent from bead to bead and
   reflect fluctuations and drifts in the experimental settings, mostly
   temperatures. In effect, they allow measuring the baseline fluctuation of
   the :math:`z` measures.  The baseline fluctuations can thus be removed by
   subtracting these beads'signal from others.

Cleaning Indicators
===================

A Noise Indicator, :math:`\sigma[HF]`
-------------------------------------

This indicator is used throughout the software. It tries to measure the
uncertainty in :math:`z` values without being subject to baseline (low
frequency) fluctuations. This is done by:

#. taking the derivative of the signal, :math:`\frac{dz}{dt} = z(t)-z(t-1)`,
#. for each cycle, measuring the median deviation,
   :math:`\mathrm{median}_{t}(|\mathrm{median}_{t}(\frac{dz}{dt})-\frac{dz}{dt}|)`,
   a robust form of the standard deviation.
#. taking the median of these values over all cycles. This last median means
   that :math:`\sigma[HF]` is not affected by a few missbehaving cycles.


A Size Indicator, :math:`\Delta z`
----------------------------------

The extension is the difference between the initial phase (1) - when magnets
are at 10 pN and beads should be double stranded - and the opening phase (3) -
when magnets are above 18 pN and beads should be single stranded. The exact
formula relies on medians to make the measure more robust to outliers whether
in cycles and frames:

.. math::

    \Delta z = \mathrm{median}_\mathrm{cycles}(
                \mathrm{median}_\mathrm{t \in \phi_3}(z)
                -\mathrm{median}_\mathrm{t \in \phi_1}(z))

Subtracting Fixed Beads
=======================

Beads are defined as fixed if:

#. Their high frequency noise is low, :math:`\sigma[HF] < 0.006 \mathrm{nm}`.
#. Their extension :math:`\Delta z < 0.035 \mathrm{nm}`.
#. Their stability from cycle to cycle, measured as told below.

