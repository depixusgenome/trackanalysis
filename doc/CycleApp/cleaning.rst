.. include:: ../utils.rst
.. include:: ../CycleApp/cleaning_utils.rst

=============
Data Cleaning
=============

.. figure:: ../_images/cleaning.png

    The impact of different signal analysis filters on |z| values for a
    given bead. The color blue is used for accepted frames, other colors
    indicate that the frame or even the whole cycle has been discarded.

.. hint::

    This tab and the |Beads| have exactly the same controls and the same
    information. Simply one shows all cycles super-imposed and the other all
    cycles side-by-side.

The goal of this tab is to:

#. define the setting allowing an automated cleaning of all signals. Beads
   failing this automated cleaning are categorized either as *bad* or
   *missing*.
#. define which beads can be considered *fixed*. Such beads are *probably*
   bound non-specifically to the surface and cannot ever open (become
   single-strand). Their behavior is mostly consistent from bead to bead and
   reflect fluctuations and drifts in the experimental settings, mostly
   temperatures. In effect, they allow measuring the baseline fluctuation of
   the |z| measures.  The baseline fluctuations can thus be removed by
   subtracting these beads'signal from others.

.. hint::

    Downsampling has no effect on data cleaning or alignment. In consists only
    in reducing the number of points displayed in the plot. The latter makes
    displays a little more fluid.

Cleaning Indicators
===================

A Noise Indicator, |NOISE|
-------------------------------------

This indicator is used throughout the software. It tries to measure the
uncertainty in |z| values without being subject to baseline (low
frequency) fluctuations. This is done by:

#. taking the derivative of the signal, :math:`\frac{dz}{dt} = z(t)-z(t-1)`,
#. for each cycle, measuring the median deviation,
   :math:`\mathrm{median}_{t}(|\mathrm{median}_{t}(\frac{dz}{dt})-\frac{dz}{dt}|)`,
   a robust form of the standard deviation.
#. taking the median of these values over all cycles. This last median means
   that |NOISE| is not affected by a few missbehaving cycles.

This can be measured independently using one or a selection of phases.
Depending on the user's settings this is either:

#. *frame-wise* uses phases 1 throught 5 included.
#. *phase-wise* measures the |NOISE| in phases 1, 3 and 5 independently and
   returns their average.

The reason for these two options is historical. The default *frame-wise*
measurement is currently in use until the effect of the second one can be
ascertained. The *frame-wise* measurement suffers from the following:
   
#. Transition phases 2 and 4 contribute. This is not ideal since the main
   movements during these phases are expected whereas the |NOISE| is supposed
   to measure random noise.
#. The exact value of |Noise| will vary from experiment to experiment for a
   same bead depending on the relative duration of phases from 1 to 5 in each
   experiment. A better measure of the noise would be intrinsic to the bead
   rather than experiment dependant.

In the situation when the framerate is higher than 30Hz, that of the optical
instruments, the signal is downsampled appropriately. In practice, this should
only affect the micro-wells data.

A Size Indicator, |DZ|
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

#. Their high frequency noise is low, :math:`0.1 \mathrm{nm} < \sigma[HF] < 6 \mathrm{nm}`.
#. Their extension :math:`\Delta z < 35 \mathrm{nm}`.
#. The number of drops in phase 5 :math:`(\sum\frac{dz}{dt} < 10 \mathrm{nm}) <`
   number of cycles.
#. Their stability from cycle to cycle, measured as defined below must be less
   than :math:`10 \mathrm{nm}`. This stability roughly means that no more than
   10% of measures can lie farther than :math:`10 \mathrm{nm}` away from other
   measures.

Beads detected as fixed are listed in the text above the *fixed bead* input.
They are listed in a prefered order. The user might select 5 from the list and
use them to subtract the baseline signal.

The baseline is measured using all cycles in all selected beads in the
following manner:

#. For each bead and cycle independently, a bias is estimated as the median of
   z values in phase 5.
#. Theses biases are subtracted from each cycle. This means that all *doctored*
   cycles on all beads tend to cross the x axis at the same time in phase 5.
#. For each position :math:`t` in time individually, we estimate the baseline
   position as the median all *doctored* values at that time:

.. math::
    \mathrm{baseline}(t) = \mathrm{median}_{\mathrm{beads}}
    (\mathrm{z}(t, \mathrm{bead})-\mathrm{bias}(\mathrm{cycle}, \mathrm{bead}))

The bias removal means that this reconstructed baseline is not affected by low
frequency fluctuations occurring over more than the timescale of a cycle. Nor
is it affected by each bead having it's own baseline mean. Roughly, all that is
required for the reconstructed baseline to be meaningfull is that at each
cycle more than 50% of beads behave the same way.

Fixed Bead stability
--------------------

As stated above, *fixed beads* should all behave the same way. A similar test
is run over each bead on all cycles. The bead stability is a measure of how
much all cycles in a bead have the same behaviour. Computations are similar to
the reconstruced baseline, but considering a single bead:

#. For cycle independently, a bias is estimated as the median of z values in
   phase 5.
#. Theses biases are subtracted from each cycle. This means that all *doctored*
   cycles on all beads tend to cross the x axis at the same time in phase 5.
#. For each position :math:`t` in time individually, each cycle starting at
   :math:`t=0`, we estimate the varability as the median deviation of all
   *doctored* values. The overall stability is the median deviation of that:

.. math::
    \mathrm{stability}(t) = \mathrm{median deviation}(\mathrm{median deviation}_{\mathrm{cycles}}
    (\mathrm{z}(t, \mathrm{cycle})-\mathrm{bias}(\mathrm{cycle})))

To be quite exact, instead of a median deviation, we use the distance from the
5th to the 95th percentile.

Data Cleaning
=============

A number of filters allow discarding individual z values:

* |absz|: sets a threshold on outliers. Measures sitting too far from the
  baseline  are discarded.
* |dzdt|: allows discarding measures too far from the measure
  just before or just after. If a bead jumps up by 3 µm and then back down, the
  measure is discarded.

Most other filters allow discarding badly behaving cycles:

* |DZ|: allows discarding that stay closed and beads that have too
  long a strand.
* |NOISE|: allows discarding noisy cycles or those for which
  measures were not recorded (z is constant).
* `% good`: allows discarding cycles that have too many missing values.
* |pingpong| allows discarding cycles with values which jump up and down.
* |phasejump|: for SDI instruments, allows discarding cycles
  with too many phase-jumps (showing as 'spikes' on the cycles).

Finally two filters are performed over all cycles:

* `% good`: the whole bead is discarded unless a given percentage of frames
  still exist after cleaning. This is the same percentage as for discarding
  cycles. This filter is actually applied three times:
  
    * after all filters above,
    * after aligning cycles and discarding those which could not be aligned.
    * after post-alignment cleaning (|clipping|).

* `% non-closing`: requires that a minimum number of cycles close entirely
  before reaching the end of phase 5. This will not always happen either
  because of a structural blockage, which should be detectable using ramps, or
  because of one or more oligos binding too long and too often considering the
  time spent in phase 5.

The bottom-left table displays filter values for all cycles. In particular, the
cycles which have been discarded are marked as such in the right-most column.
The colored spot on the column titles follows the same code as on the plot. 

Plot Colors
-----------

The plot's |z| values are color-coded as follows:

* Values without problems are blue.
* |NOISE|: noisy cycles are yellow.
* |DZ|: cycles with an incorrect extent are orange.
* Cycles with too few correct values are pink.
* |pingpong| cycles with too few correct values are red-brown.
* Non-closing cycles are dark orange.
* |absz| and |dzdt|: outliers are marked in red.
* Cycles which could not be aligned are dark gray.
* |clipping|: outliers as defined by the range of values in *aligned*.
  Such cycles are marked in purple.

These colors are reported again in the table, using colored dots in the column
headers.

Cycle Alignment
===============

Because of the baseline's variability, cycles need realigning. We use values
from phases 1 and 3 to do so. In theory, using phase 3 should provide us with
best results since this is the phase when the magnets are closest to the beads,
thus when the magnetic gradient is the harshest, and the pull it exerts on the
beads reduces Brownian motion the most. In practice, we find that:

* For some cycles, the hairpin doesn't open, in which case z values in phase 3
  are necessarily small.
* There can be some variability in the bead's full extent, due either to some
  change in the way the oligonucleotide sequence is attached to the surface or
  the bead, or due to secondary structures forming in te sequence.


The *best* alignment
--------------------
Empirically, the best cycle alignment is performed by computing the biases per
cycle as follows:

* Default biases are equal the median of phase 3 for each cycle less the median
  extent over all cycles. This *normal* cycles will tend to start at 0 and
  reach the bead's full extent at phase 3.
* For those *corrected* cycles with both phase 1 and the end of phase 5 not
  aligning with other cycles (*i.e.* z ≠ 0), we change their bias to the median
  value in phase 1. Such cycles are those cycles when the bead doesn't open.
* We discard cycles for which values in phase 7 (magnets at 5 pN) are too far
  from others. This filter is loose because phase 7 has a very high Brownian
  motion and values are particularly unstable.

The user can select the alignment described above or others:

#. `∅`: No alignment
#. `best`: the procedure described above.
#. `φ1`: aligning all cycles on phase 1.
#. `φ3`: aligning all cycles on phase 3.

The median bias
---------------

Alignment values are reported in the table for each cycle. Only their value
relative to one another is truly important. For the sake of clarity, in the
table, values are reported after subtracting the median. In plots, the median
bias is set such that the baseline is at zero.

Post alignment cleaning: |clipping| 
-----------------------------------

Some data-cleaning is performed post-alignment: values in phase 5 are discarded
which sit below the phase 1 values or above phase 3 values. The exact thresholds are:

* low:  :math:`\mathrm{median}_\mathrm{\phi 1}(z)-\sigma[HF] \alpha`
* high: :math:`\mathrm{median}_\mathrm{\phi 3}(z)`

The value :math:`\alpha` can be set from the *advanced* settings. Values
reported in the table is the percentage of outlier frames in phase 5.

Advanced Options
================

The following settings can be moved by the user. Should that happen, the
default settings will be indicated in parenthesis to the left of the input box.

Fixed Beads
-----------

* |DZ|: set the maximum extent a bead may have and be considered fixed.
* |NOISE|: set the maximum noise a bead may suffer from.
* :math:`\phi 5` repeatability: sets how close together to the median cycle
  profile 90% of values must sit for a bead to be considered fixed.
* |SUBTRACTION|

Undersampling
-------------

Undersampling can be done per frame or per cycles.

The first two elements allow undersampling a track file per frame. By default
track files are undersampled so as to reach a sampling rate of about 30Hz. The
sampling is integral: for an initial rate of 100Hz, the values will be
undersampled by a factor 3 - not 3.333 - reaching a final sampling rate of 33Hz
rather than exactly 30Hz. The sampling can be done by averaging the frames or
by picking the first one. If a low-pass filter with a cut-off below 30 Hz was
applied to the initial data, the latter is preferable. With a cut-off above
30Hz, the former is preferable.

The last 3 elements allow discarding cycles by defining:

1. the first cycle to take into account, starting at zero (i.e setting 1
   discards the first cycle).
2. The last cycle to take into account (i.e. setting 100 disards the
   101st cycle and all the later ones).
3. The increment: an increment of 1 takes all cycles into account, an increment of 2
   discards every other cycle, etc...

Cleaning
--------

The first element allows choosing the exact strategy for measuring the |NOISE|.
See the setion on |NOISE| for more details. In short:

* *frame-wise* is the current default. As stated earlier, it suffers from many drawbacks.
* *phase-wise* is under investigation but is expected to be less dependant on
  experimental settings and better correlated to intrinsic bead
  characteristics.

The next 8 elements are repeats of inputs available in the main window. The
advantage of having them here is simply to have their default value indicated
again. The following are additionnal:

* `% aligned cycles`: defines the minimum percentage of successfully aligned
  cycles for a bead to be correct.
* |pingpong|  discarding cycles with values which jump up and down.
* `Cycles are closed if |z(φ1)-z(φ5)| <`: the maximum distance from phase 1
  that the last values in phase 5 may sit for the cycle to be considered as
  *closed*.
* |CLIPPING| 
* `% good frames`: defines the minimum percentage of remaining frames after
  cleaning and post-alignment cleaning.

Theme
-----

The settings here change only the aspect of the windows. Color themes are
available which will be applied to plots in all tabs. This tab's plot dimension
can also be set. Unfortunatly, the change will only occur upon relaunching the
application.
