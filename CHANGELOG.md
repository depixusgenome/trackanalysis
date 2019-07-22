# CycleApp
## cycles_v6.12

### Peaks

One can now add 'kmer' or '3mer' or '4mer' to the list of oligos. In such a
case the track file names is used to automatically find the oligos. The
expected format is a track file name containing elements such as 'atcg 2nM' or
'aaa 3pM'. The concentration must come after the oligos. It may or may not be
separated by an underscore.

## cycles_v6.11

* 2019-07-17 09:20:39 +0200  (tag: ramp_v2.3.1, tag: cycles_v6.11.1)
* 2019-07-10 10:30:59 +0000  (tag: ramp_v2.3, tag: cycles_v6.11)

### Cambridge Features

The following were requested for better processing µwells data:

1. It's now possible to undersample the data. Microwells data is usually
   measured at a rate of 100Hz with a low-pass hardware filter with a low
   cut-off, possibly lower than 30Hz. This affects the behaviour of algorithms.
   In order to compare it to picotwist/SDI data, it was requested the data be
   resampled to a 30Hz rate. From the *cleaning* tab, it's possible to set the
   target frame rate as well as how values are aggregated.

2. The temperatures in the *QC* tab can be extracted to CSV using a button
   above all plots.

## cycles_v6.10

* 2019-06-28 06:38:36 +0000  (tag: ramp_v2.2, tag: cycles_v6.10)

### Peaks

Two pieces of information have been added: the baseline and the singlestrand
peak positions. These are left empty if not detected.

In the advanced menu, it's now possible to set the range of stretches and biases
considered for fitting to the sequences. The three new entries are:

* **Expected stretch (bases per µm)** is the central value in the range of tested stretches.
* **Stretch range (bases per µm)** is the range of stretches explored both above
  and below the expected stretch.
* **Bias range (µm)** is the range of biases explored both above and below the the
  bias default value. The latter can be the baseline, the single-strand peak or
  zero depending on the list of *oligos* provided.

## cycles_v6.9

* 2019-06-12 11:15:11 +0200  (tag: cycles_v6.9.3)
* 2019-06-12 10:20:08 +0200  (tag: cycles_v6.9.2)
* 2019-06-11 11:51:58 +0200  (tag: cycles_v6.9.1)
* 2019-06-06 16:12:58 +0200  (tag: cycles_v6.9)

### Cleaning

Colored spots have been added to the table of cycle statistics to facilitate
reading the plots. The following columns were added or changed:

* *alignment*: the alignment value, with a median enforced at 0 for clarity.
There could be NaN values wich imply that the cycle could not be aligned and is
thus discarded.
* *z ∉ range(φ₁ → φ₃)*: the percentage of frames sitting outside a range
defined using median values in phases 1 and 3. Theses frames are discarded.
This might be refered to as the *clipping* stage.
* *discarded*: the percentage of frames discarded wether through data cleaning,
alignment or clipping.

### Micro Well Data

Added automated detection of LIA data: the files must have a '.txt' extension
and the directory must be either the same or vary only by replacing 'trk' by
'txt' in the path: a track file in `C:\Users\MyName\Data\trk\2019010101.trk`
will have the software look for files `C:\Users\MyName\Data\txt\2019010101.txt`
or `C:\Users\MyName\Data\trk\2019010101.txt`.

Can now deal with any polarity in µV as well as non-opening cycles.

Furthermore, the σ[HF] is now normalized depending on its frame rate: the
signal used to estimate σ[HF] is downsampled to a rate of 30Hz.

## cycles_v6.8

* 2019-04-23 10:20:10 +0200  (tag: cycles_v6.8)

### Peaks

To improve fit quality, false positives, i.e unidentified peaks are now taken
into account when computing the score. This changes the order of best hairpins.
It may have an effect on the stretch and bias values although rarely. One can
return to the previous behaviour using the advanced menu.

A number of display bugs were corrected which were added at version 6.4. These
resulted in incorrect axes and peak labeling being displayed on-screen. The
excel files were not affected.


## cycles_v6.7

* 2019-04-19 10:20:10 +0200  (tag: cycles_v6.7)

### Micro-well data

One can now load micro-well lock-in amplifier data into the application. Simply
open the track file, then open the text file. The information from both files
is synchronized to the best of the available information. See the documentation
for more details.

## cycles_v6.6

* 2019-02-25 15:41:46 +0100  (tag: cycles_v6.6.5)
* 2019-02-08 08:41:46 +0100  (tag: cycles_v6.6.4)
* 2019-02-06 14:30:24 +0100  (tag: cycles_v6.6.3)
* 2019-02-06 11:11:46 +0100  (tag: cycles_v6.6.2)
* 2019-02-06 09:34:19 +0100  (tag: cycles_v6.6.1)
* 2019-02-05 15:54:58 +0100  (tag: cycles_v6.6)

### Oligos

Bindings on the forward (backward) strand can be selected on an oligo basis by
prefixing the oligo with + (-).

## cycles_v6.5

* 2018-12-21 11:58:19 +0100  (tag: cycles_v6.5)

###  Peaks

In the table, the *Strand* column now reports the binding orientation as as
well the sequence around either the theoretical position or the experimental
position when no theoretical position was found. The sequence is marked in bold
for bindings on the positive strand and italic bold for the negative strand.

### Consensus

The goal of this **new** tab is to show a consensus on all beads attached to the
current hairpin. If none has been indicated, the tab is of lesser interest.

## cycles_v6.4

* 2018-12-13 10:58:19 +0100  (tag: cycles_v6.4.1)
* 2018-12-12 22:38:58 +0100  (tag: cycles_v6.4)

### Hairpin Groups

This new tab displays multiple beads at a time. There are 3 plots:

* A scatter plot displays beads on the x-axis and hybridisation positions on the y-axis.
* The two histograms display durations and rates of selected hybridization
  positions. The user can select positions graphically using the scatter plot.
  This will update the histograms.

Beads displayed are:

* the current bead,
* all beads which were affected to the currently selected hairpin,
* unless the user discarded them from the display (2nd input box on the left).

Computations are run in the background using 2 cores. Beads will appear
automatically once computed. To disable this, go to the advanced menu and set
the number of cores to zero.

### Cleaning

Since version 6.3, values in phase 5 which are not between median positions in
phase 1 and 3 are discarded. In some situations, this leads to the bead loosing
a majority of values.  This can happen with the SDI when there are phase jumps
in the tracking algorithm. The cleaning tab will now report such situations.

## cycles_v6.3

* 2018-12-10 09:35:52 +0100  (tag: cycles_v6.3.2)
* 2018-12-04 09:35:52 +0100  (tag: cycles_v6.3.1)
* 2018-11-22 15:51:52 +0100  (tag: cycles_v6.3)

### Documentation

Documentation was added to both CycleApp and RampApp:

* The changelog should display at every new version.
* Some documentation is available throught the "?" button in the toolbar.

### Peaks

#### Selecting peaks: probes, baseline and singlestrand

**Warning:** The way in which peaks to consider in fits can be set has changed.

Prior to this version, one could go to the *advanced* menu and select whether
to use the baseline position (`z=0`) and/or the single strand position in fits.
Starting from *v6.3*, this is now set throught the list of probes ( oligos):

1. to select the baseline position, add `0` to the list of probes,
2. to select the single strand position, add `singlestrand` or `$` to the list
   of probes.

If, and only if, the single strand position is not used, the software will try
to detect that position and discard it from the list of hybridizations. This
detection relies on phase 4 being a *slow* ramp. Nothing is done should the
ramp be too fast.

When the single strand is selected, the cost function used to determine the
best stretch and bias has changed: stretches and biases which set some peaks
above the single strand position are disadvantaged. The same is done for the
baseline position when selected.

These changes were made in order to improve the situation with microRNA. They
should improve any other situation where there are less than 3 reference
positions. In such a case, consider using `singlestrand`

#### Probe positions, a reminder

By default, the probe position is defined as the binding base closest to the
loop. This is not valid for methylation detection. In that case, use a `!` to
indicate that the base right after should be the probe position. For example
the position for `cc!wgg` is in the middle of the sequence. This feature exists
since version *v4*.

### Cleaning

Fixed beads are those beads with a *small* extension (`Δz < 0.035`), little
noise (`σ[HF] < 0.006`) and a good signal stability, or repeatability, from
cycle to cycle. The latter means that a median behavior is computed and beads
are defined as fixed only if 95 percent of cycles never stray too far (`δz < 0.01`)
for too long (`< 90%` of frames) from that median. These various parameters can
now be set by the user.

## cycles_v6.2

* 2018-11-15 10:21:24 +0100  (tag: cycles_v6.2.2)
* 2018-11-14 22:46:11 +0100  (tag: cycles_v6.2.1)
* 2018-11-14 15:41:50 +0100  (tag: cycles_v6.2)

### Peaks

By default, frames in phase 5 with values below phase 1 or above phase 3 are
discarded. This is done after cleaning, thus bead selection, and cycle alignment.

When multiple hairpins are provided by the user and oligos have been specified,
a few things can happen:

1. if the user locks the hairpin to use for a given bead, then the dropdown
   menu will only allow selecting that specific choice.
2. the user does not fix the hairpin, then the software:

    1. sorts the possible choices from best to worst (₁, ₂, ₃, ...),
    2. specifies the hairpins which could not be fitted (✗),
    3. indicates which choice of hairpin was made by the user in the reference track.

When producing a report, the software will classify some beads as failed (✗).

A failure (✗) occurs when the phase 3 values are different from from the
hairpin size.  The conversion factor used is 1 base/µm.

## cycles_v6.1

* 2018-11-12 22:15:27 +0100  (tag: cycles_v6.1.1)
* 2018-11-12 15:12:50 +0100  (tag: cycles_v6.1)

### Peaks & Cycles

This new tab is similar to the *Peaks* tab, offering slightly different plots.
It also allows a few more options on the output: font size and grids can be set
from the *advanced* menu. 

## cycles_v6.0

* 2018-11-09 15:42:32 +0100  (tag: cycles_v6.0.3)
* 2018-11-09 14:51:19 +0100  (tag: cycles_v6.0.2)
* 2018-11-08 15:26:32 +0100  (tag: cycles_v6.0.1)
* 2018-11-08 15:11:56 +0100  (tag: ramp_v2.0, tag: cycles_v6.0)

### General

The gui has been updated, in particular the *FoV* and *QC* tabs as well as the
*advanced* menus. In the latter, it's now possible to select a number of styles
for plots. It's also possible to define the y-axis ranges of plots.

Another change is when multiple files are loaded, the names used to differenciate
them are automatically simplified, removing elements common to all files (elements
are separated by underscores).

### QC

This tab now contains better summaries, also available in *RampApp*:

1. Status of beads: beads can be either *ok*, *fixed*, *bad*, or *missing*.
2. Sizes of beads: beads are clustered by bins of a given size. The bin size is
set by the used using a slider.

### Cleaning

It's now possible to discard all bad beads in one go. Simply write `bad` into the
toolbar text entry for discarding / selecting beads. Other categories are `ok`,
`missing` and `fixed`. The latter 2 categories are included into the `bad`category.

### Peaks

It's now possible to manually select the sequence, a stretch and a bias for each
bead individually. When a sequence is manually locked-in in the reference track,
that sequence is marked as such when looking at other tracks.

When multiple hairpin sequences are provided in a fasta file, we now use a
median bead extension to select only meaningful sequences. Thus a 5kb bead will
discard sequences < 5kb and only consider those extending to ~5kb. When only
one hairpin sequence is provided, the behaviour is unchanged.

Furthermore, computations are now cached.

## cycles_v5.3

* 2018-10-16 15:12:02 +0200  (tag: cycles_v5.3.1)
* 2018-10-15 13:10:46 +0200  (tag: cycles_v5.3)

The *cyclesplot* application was removed. It's already part of* **hybridstat*.
Similarly, the *_chrome* applications have disappeared as a third party library
now makes these redundant.

### Speed

A number of algorithms have been ported to c++: cleaning and event detection.
This is in order to speed up computations.

### Peaks

The user can now elect to discard the *single-strand* peak from the data. This is
done through the *Advanced* menu.

### Track Management

Loaded tracks can be discarded using the same toolbar menu as for selecting them.

## cycles_v5.2

2018-07-17 12:08:28 +0200  (tag: cycles_v5.2.3)
2018-06-25 11:50:57 +0200  (tag: cycles_v5.2.2)
2018-06-22 15:53:10 +0200  (tag: cycles_v5.2.1)
2018-06-15 22:30:54 +0200  (tag: cycles_v5.2)

### Theme

The user can now change the background color using the *Advanced* menus. The
size of the figures can also be adapted although the application must be
restarted for this to take effect.

## cycles_v5.1

* 2018-04-30 09:07:33 +0200  (tag: cycles_v5.1)

### Peaks

The user can now add/remove subtracted beads from the advanced menu. She can also
change the cycle alignment strategy.

## cycles_v5.0

* 2018-04-25 15:31:20 +0200  (tag: cycles_v5.0.1)
* 2018-04-17 13:10:26 +0200  (tag: cycles_v5.0)

### Cleaning

Tests were made more stringent:

* σ[HF] is tested over phases 1 to 5 instead of 5 only
* the min population is tested over phases 1 to 5 instead of 5 only

A new test was added. It is noted as `∑|dz|` and does the following:
* computes the absolute value of the derivative of z in time,
* discards values lower 1e-2 (~ 3 times the usual precision),
* sums the remaining values.

Discarding small values meanst that the brownian motion is ignored. What
remains are the movements due to the magnets and the hybridizations. The sum of
those should be twice the dynamic range. We discard cycles for which the sum
exceeds 3 times the dynamic range. This should only occur when the bead tracking
is not working.

A *downsampling* slider was added. The effect is to reduce the number of points
displayed: a value of 5 means that only 1 out of 5 points are considered. The
downsampling is performed on *displayed points*, after computations. It has an
effect on the display only.

### Alignment on phase 5

The alignment on phase 5 uses events only. Cycles are aligned such that the
event density is locally increased. Unfortunatly, the algorithm failed in cases
when 2 zero positions coexist in a file. In such a case, cycles were sometimes
moved such that only one zero position remained, doubling the number of other
peaks. The algorithm is no longer used.

A new algorithm for aligning on phase 5 has been set up:

* peaks are found, without any prior phase 5 alignment.
* cycles are aligned on those peaks, peak positions are recomputed.
* step 2 is repeated 10 times.
* peaks are found anew using aligned cycles.

The advantage of the new algorithm is that peaks cannot merge anymore.

### Speed

The mechanics for displaying tabs have changed. These display much faster. The
downside is that bugs will occur if the user switches between tabs too fast. Any
visible bug can be cured by *slowly* switching tabs a couple of times.

## cycles_v4.11

* 2018-01-30 10:01:16 +0100  (tag: cycles_v4.11.3)
* 2018-01-29 11:26:15 +0100  (tag: cycles_v4.11.2)
* 2018-01-23 14:37:28 +0100  (tag: cycles_v4.11.1)
* 2018-01-23 14:28:23 +0100  (tag: cycles_v4.11)

### Quality Control

Redefined fixed beads as having all their cycle extension at less than 0.15.

### Cleaning

#### More robust computation of the bead precision (σ[HF])

The precision is now the median of the σ[HF] measured on each cycle between phases
1 and 5 included. We thus get rid of noisy and non-representative phases as well as
improving the robustness of the measure.

#### Too few cycles reach 0 in phase 5
When too many cycles (> 90%) never reach 0 before the end of phase 5, the bead is
discarded. Such a case arises when:

* the hairpin never closes: the force is too high,
* a hairpin structure keeps the hairpin from closing. Such structures should be
detectable in ramp files.
* an oligo is blocking the loop.

## cycles_v4.10

* 2018-01-04 09:25:16 +0100  (tag: cycles_v4.10)

In advanced configuration menus, the default value is indicated if ever the
value is different.

Subtracted beads are now displayed explicitly in xlsx reports.

## cycles_v4.9

* 2017-12-21 11:32:52 +0100  (tag: cycles_v4.9.5)
* 2017-12-13 11:10:43 +0100  (tag: cycles_v4.9.4)
* 2017-12-12 13:53:25 +0100  (tag: cycles_v4.9.3)
* 2017-12-12 09:34:38 +0100  (tag: cycles_v4.9.2)
* 2017-12-06 13:47:42 +0100  (tag: cycles_v4.9.1)
* 2017-12-06 08:04:40 +0100  (tag: cycles_v4.9)

SDI track files can now be displayed as efficiently as Picotwist files

## cycles_v4.8

* 2017-12-05 11:32:52 +0100  (tag: cycles_v4.8)

### Field of View

Fixed beads are displayed in brown. A bead is detected as fixed if its extension
is less than 0.5 µm on *all* cycles.

### Quality Control

A tab has been added providing some quality control indicators.

On the right is the list of messages issued from cleaning the beads. This was
previously in a *Messages* tab. The summary has been worked on, now providing a
list of fixed beads: beads with an extension less than 0.5 µm for *all* cycles.

On the left are 4 plots:

1. The normalized bead extensions are displayed as a function of the cycle number.
2. The sample's temperature is displayed as a function of the cycle number.
3. The heat sink's temperature is displayed as a function of the cycle number.
4. The Peltiers' temperature is displayed as a function of the cycle number.

Normalized bead extensions consist in  the difference between median values for
phase 3 and phase 1 normalized to their median, independently for each bead.
These values should be around zero with a deviation less than twice the σ[HF].
The information for this first plot is displayed as:

* Circles indicate the normalized extension for a given bead and cycle.
* Bars at each cycle indicate population percentiles 25% and 75%.
* A line within each bar indicates the median for that cycle.

For all four plots, median value as well as the first and last decile are
displayed was horizontal dashed lines.  Should the the range from the first to
the last decile exceed 0.2°C (first three plots) or 15 nm (last plot), **that
plot will be circled in red**.

### Peaks

Added a *Reference* dropdown button for selecting a track as reference. For all
other tracks, the *z* axis is scaled to the reference's for each bead
independently such that as many peaks from the *reference* match the peaks in
the current track.

Added some information on the peaks graph:

* The *blue* dots along the *blue* line are the positions of events found.
* The areas colored in *bisque* is the reference's peaks, should there be a reference.

## cycles_v4.7

* 2017-11-06 14:29:55 +0100  (tag: cycles_v4.7)

### Menu

Added access to previously loaded tracks.

### Bugs

* Could not read identification files

## cycles_v4.6

* 2017-10-30 14:12:14 +0100  (tag: cycles_v4.6)

### Bead Selection

It's now possible to either select beads to discard or beads to keep. In the
toolbar, click on the '=' or '≠' button to do one or the other.

### Field of View

Beads now have a color:

* *green*: good beads.
* *orange*: beads which the automated cleaning will discard.
* *red*: beads discarded by the user.

A tooltip is shown on orange beads showing the warnings issued by the automated
cleaning. The tooltip on other beads is the bead's σ[HF].

### Hybridstat Reports

The *Ratios* column has been split into 2 columns:

* *Identified Peak Ratio*: identified peaks / Expected peaks
* *Unknown Peak Ratio*: Unknown peaks/ Found peaks

## cycles_v4.5

* 2017-10-18 08:40:04 +0200  (tag: cycles_v4.5.1)
* 2017-10-16 14:08:03 +0200  (tag: cycles_v4.5)

### User Interface

The graphics library has been updated. It reports some improvements on speed of
execution.

Graphics have been moved around in order to circumvent sizing bugs which still
havn't been solved.

### Cleaning

* Frames with missing values on both sides are discarded.
* Intervals of values with missing values on both sides are discarded if:

    1. the width of the interval is less than 10,
    2. there are 2 missing values on each side,
    3. more than 80 percent of the interval derivatives are above 0.1 µm

The settings can be changed only by editing the user configuration file.

### Cycles

#### User Interface

The bias could not be set lower than the lowest z value in the histogram. One can
now go 50nm below that.

Highlighting a cycle now requires selecting a point. This makes the interface
more responsive the rest of the time.

#### Event Detection
Events smaller than about 6 frames were never detected. We can now detect 5-frames
events reliably and 4-frames events sometimes.

Events tended to be split: multiple events were found in a same cycle at a same
z value. These are now merged back into a single event using the following rules:

* *statistical distribution*: Event populations are hypothesized to be normally
  distributed. To see whether 2 neighbouring events should merge, a statistical
  test to see how their averages and standard deviations aggree. Prior to this
  version, the standard deviation was considered to be known and estimated over
  the whole bead. This prevented events at high z, where the noise is greater,
  from merging.
* *population count*: 2 neighbouring events are merged if at least 66 percent
  of the population of one has its z values between the min and max of the
  other.
* *range comparison*: 2 neighbouring events are merged if the intersection of their
  range of z values occupies 80 percent or more of one of these ranges.

### Hybridstat

#### Fitting Beads

A new fitting algorithm is available: see the *Advanced* menu. The 2 available
algorithms are now:

* *Gaussian distance*: the algorithm described at tag *cycles_v4.4*
* *Exhaustive search* (**default**): the concept is to iterate over all 2 pair
  of one experimental peak with a theoretical counterpart and
  
  1. Estimate a stretch and bias using those 2 pairs
  2. Pair-up experimental peaks with theoretical ones using this 1st approximation.
  3. Re-estimate the stretch and bias using a linear regression on the new pairs.
  4. Pair-up experimental peaks with theoretical ones using this 2nd approximation.
  5. Re-estimate the stretch and bias using a linear regression on the new pairs.

The main difference is in the way potential stretch and biases are found. The
new approach is quasi-certain to hit upon a good 1st estimate. It will run for
very long unless there are less than 10~20 theoretical peaks.

#### Applying Constraints

Some help is provided in applying constraints to stretch and biases:

* *creating a new constraints file* can be done by simply typing the name of a
  new file in the *Id file path* input box. The new file will open using excel.
  It will contain the following columns:

  1. *Bead*: the bead number. One does not need to provide all beads. Numbers
     in the excel file not in the track file, and vice-versa, will
     automatically be ignored by *CyclesApp*.
  2. *Reference*: the hairpin reference name. This is useful if there are
     multiple hairpins in the mix. It still must be indicated even if there is
     only one.
  3. *Stretch (bases/µm)*: the number of bases per micrometer. Please beware of
     the units.
  4. *Bias (µm)*: the zero position, in micrometer. Please beware of the units.

* *updating a constraints file* will affect *CyclesApp* within half a second:
  The software checks the file modification date and reloads the data
  accordingly. Please note that an update is a modification followed by a
  file *save*.

The files do not need to be created through the new feature. They do require to
have the same structure: at least 4 columns *bead*, *reference*, *stretch* and
*bias* in a *summary* tab. This means a previously created excel report can
also be used.

## cycles_v4.4.3

* 2017-09-28 09:59:18 +0200  (tag: cycles_v4.4.3)
* 2017-09-27 08:24:06 +0200  (tag: cycles_v4.4.2)

### Bugs

* Could not open a SDI track file.
* Could not launch the chrome version.

## cycles_v4.4.1

* 2017-09-27 08:13:26 +0200  (tag: cycles_v4.4.1)

### Cleaning & Xlsx reports

* Beads responsible for an automated warning are systematically discarded from
  xlsx reports. The only way to have them in the reports is to update the
  filters in the *Cleaning* tab.

### Bugs

* Saving an xlsx file from a tab other than *Cycles* or *Peaks* could result in
  a crash.
* If beads responsible for an automated warning (in the messages tab) were not
  discarded, saving an xlxs file resulted in a crash


## cycles_v4.4

* 2017-09-18 06:07:28 +0000  (tag: cycles_v4.4)

### Messages

Messages issued by the automated cleaning are collected in an independant task.

### Hybridstat

Stretch and bias is now estimated in 3 steps:

1. A global cost function is used to find an approximate stretch and bias.
   This function is, where X and Y are 2 series of peak postions:

        F(X, Y) = 1 - R(X, Y)/sqrt(R(X, X) R(Y, Y))
   with

        R(X, Y) = Σ_{i, j} exp(-((x_i -y_j)/σ)²)


2. Peaks from X and Y are paired together using the approximate stretch an bias.
3. A linear regression is used on the pairs to estimate the best stretch and bias.

### Bugs

* Beads without a calibration file are discarded.
* Regression: excel reports could not be used as constraints anymore
* The cleaning tab had various visualization bugs.
* Cleaning was not correctly ported to all tabs.

## cycles_v4.3

* 2017-09-05 10:20:29 +0200  (tag: cycles_v4.3)

### Field of View

The field of view (FoV) is now available in its own tab. The calibration file
for the current bead is also displayed. One can select a bead by simply
clicking on the FoV.

### Automated Data Cleaning

Added an automated cleaning process. A *cleaning* tab is available which displays
which data points or cycles are missing. The criteria are:

1. For removing single data points:
    * |z - median(z)| > 5.
    * |dz/dt| > 2.
    * constant intervals: |z[n] - z[n+1]| < 1e-6 and |z[n] == z[n+2]| ...
      In such a case, only the first point is kept.

2. For removing cycles:
    * percentage of good data points < 80
    * max(z) < min(z) + 0.5
    * values are constant: σ[HF] < 1e-4
    * values are too noisy: or σ[HF] > 1e-2

These values can be updated throught the gui

### Fixed Beads

Fixed beads can be removed by going to the *Cleaning* tab and adding the number
to the *subtracted beads* input. Pressing the button on its right will add the
current bead to subtracted beads.

### Reporting

Header in summary is now in multiple columns with the most irrelevant information
set last.

Column names have changed. They are now the same in the GUI and the reports.

A *σ[PEAKS]* and a *Ratios* column has been added to the summary.

### Data Treatment

The *best* alignment has changed somewhat to better detect abnormal cycles.

### Other

Various bugs have been corrected. The warm-up time has been divided by 4.

## cycles_v4.2

* 2017-06-07 08:21:15 +0200  (tag: cycles_v4.2)

### Reporting

Previously, the number of cycles was only reported for the track file as a
whole.  Now, the number of valid cycles per bead is also reported. This number
is also used for computing hybridization rates. The latter are thus more exact.

Multiple bugs in the neighbouring sequence detection were removed.

### Peak detection

The *smearing* field found in *pias* can now be configured as well. This is the
"Peak kernel size" field in the Peaks/Advanced dialog. Roughly, the field
defines the minimum distance between two detected peaks. Peaks closer together
end-up merged together.

If "Peak kernel size" is left blank, the minimum distance is set to: σ[HF] x 2.
Such a value is computed independently for each bead. The factor '2' was set to
'1' in previous versions.

Experimental peaks are assigned their closest theoretical peak unless the
distance to one from the other is greater than "Max distance to theoretical peak".
This is available in the *Peaks/Advanced* dialog.


### Data Treatment

Alignments  in the *Cycles* tab have been improved. Choices available are:

* "ø": no alignment. This is the default when loading gr files.
* "Best": Alignment occurs on phase three then phase one cycles detected as unopened.
* "Φ₁": Alignment occurs on phase one only.
* "Φ₃": Alignment occurs on phase three only.

The *best* choice is different from the previous version which used to align
primarily on phase 1 then align phase 3 outliers on the median of phase 3.

These alignments do not rely on the detection of events as does the one which
can be de-selected in the *Peaks/Advanced* dialog.

## cycles_v4.1

* 2017-05-23 11:11:17 +0200  (tag: cycles_v4.1.1)
* 2017-05-23 11:01:41 +0200  (tag: cycles_v4.1)

### Reporting

Excel reports can be created without specifying a sequence. Any information or
column pertaining to the sequence is discarded.

Two pieces of information are addded:

* *Down Time* is the average amount of time spent with a bead completely zipped
in phase 5.
* *Events per Cycle* is the average number of events detected per cycle.

For better throughput, one should have both a low down time and multiple events
per cycle. A higher number of events per cycle will also increase the
precision on peak positions.

### Configuration

An *Advanced* button has been added which gives access to more configuration both
for the *Cycles* and the *Peaks* tab.

### Other

The application is now created stripped of source code and documentation whenever
possible. This is necessary for security reasons.

## cycles_v4.0

* 2017-05-11 08:44:49 +0200  (tag: cycles_v4.0)

### Data Treatment

Alignments can be performed on both phase 1 and phase 3 as follows:

1. Alignments are performed on phase 1.
2. Cycles with a small phase 1 to phase 3 extension are aligned using phase 3.
   That extension should be less than 0.9 time the median of such extensions.
3. Step 2 is cancelled for cycles for which the bead did not open. These are
   defined as those with a phase 3 to phase 5 extension smaller than 0.9 times
   the median of such extensions.

Alignments used to be performed on the min of a phase. It is now on the median of
a the last 15 points in a phase.

### Reporting

The *Hybridstat* allows creating an excel report. Simply save a project using
an *xlsx* extension. Computations are done in the background using as many processes
are there are cores on the host computer.

Data treatments are those selected in the *Cycles* tab.

### Sequence alphabet

The following alphabet is recognized: "a t g c k m r y s w b v h d n x u". Their
meanings are the classic ones: "aas" is the same as the of oligos ("aag","aac").

An exclamation point is added to define methylations. It must be added to the left
of the methylated base: "aa!sa" is methylated on the "s".

There are no distinctions between upper and lower cases.

### Other Features

* Beads can be discarded using comma-separated values in a text box to the
  right of the bead number.
* Beads with too high or too low a σ[HF] are discarded.
* Server GUI computations are threaded. This should improve the response time
  of the application.
* In case of failure, a message is displayed at top right of the application.
  The message is in *blue* if the failure is an expected one (incorrect file,
  ...).  Messages in *red* indicate a bug.

### Solved Bugs

* Changing the *stretch* and *bias* resulted in infinite client-server loops.
* Could not load *.gr* files.

## cycles_v2.0

* 2017-04-13 15:20:20 +0200  (tag: cycles_v2.0)

New application for viewing peaks

### Features

There are 3 tabs:

1. Bead: displays the raw bead data. Nothing more.
2. Cycles: displays cycles as in the 1st version
3. Peaks: A histogram of events is shown, similar to cycles tab, but using a
   gaussian kernel on the position. This allows peak detection:
    * The x-axis is the percentage of cycles when an event is detected (bottom)
      and their average duration (top).
    * The y-axis is the position of events in nm (left) or base number (right).
    * The kernel-smoothed histogram is the smooth blue curve.
    * Detected peaks display the percentage of cycles (blue squares) and their
      average durations (gray diamonds).
    * Global and peak-wise statistics are **repeated** in table on the left of
      the figure. Selecting a peak in the figure selects a line in the table
      and vice-versa.
    * Use the mouse to view the sequence at a given z.

The **Peaks** tab applies to the data all treatments selected in the **Cycles**
tab. It furthermore aligns cycles using phase 5 events.

### Fixed Bugs

* fasta files can be opened whatever their extension
* gr files can be opened
* With chrome, the bead number could not be typed in.

## cycles_v1.0

* 2017-03-28 08:21:25 +0200  (tag: cycles_v1.0)

New application for viewing cycles

* On the left plot:

    * Each cycle is displayed from yellow (first) to black (last)
    * The x-axis is the number of frames (bottom) or the duration in seconds (top)
    * The y-axis is in nanometers (left) or number of bases (right)
    * Use the mouse to see a given cycle.

* On the right plot:

    * The x-axis is the number of frames (bottom) or the number of cycles (top)
    * The y-axis is in nanometers (left) or number of bases (right)
    * The number of frames at a given *z* position is the gray histogram
    * The number of cycles at a given *z* position is the blue histogram. This
    is estimated as the number of cycles having 10 or more frames at that position.
    * Use the mouse to view the sequence at a given z.

    * The x-axis is the number of frames (bottom) or the duration in seconds (top)
    * The y-axis is in nanometers (left) or number of bases (right)
    * Use the mouse to see a given cycle.

* Viewing the sequence:
    * A single fasta file can be opened. It may contain multiple sequences.
    * The oligos can be selected. Using the Top/Bottom arrows should allow cycling
    over previously selected oligos.
    * The stretch and bias can be changed using either the sliders or the table
    displaying 2 positions (first and last theoretic peaks)

* Data cleaning includes:

    * alignment: either on phase 1 or phase 3
    * drift removal per bead: the correlation between cycles on a given bead is removed
    * drift removal per cycle: **use only if all beads are good!** The correlation between
    beads for each cycle is removed.

* Phase 5 can be viewed alone by selecting *Find events*.

* GR files can be loaded in 2 steps:

    * first open the corresponding *.trk* file: it is need to reconstruct exact cycle
    durations and number.
    * then open the *.gr* files. You can select all of them in one go.

# RampApp

## ramp_v2.3

* 2019-07-11 09:02:39 +0200  (tag: ramp_v2.3.1, tag: cycles_v6.11.1)
* 2019-07-10 10:30:59 +0000  (tag: ramp_v2.3, tag: cycles_v6.11)

This version changes the information displayed for ramps. It removes the last
table with fixed zmag and replaces it with one which reports how many beads
close for what percentage of their size depending on the zmag slider value.
This zmag value is materialized as a red line on the plot.

The table reporting clusters of beads per size is moved to the bottom of the
screen.

## ramp_v2.2

* 2019-06-28 06:38:36 +0000  (tag: ramp_v2.2, tag: cycles_v6.10)

### Cleaning

This version adds the *Cleaning* tab which already exists in *CycleApp*.
Results in the *Ramp* tab are affected by the cleaning: some beads are rejected
at the cleaning stage.

The raw data plots have been improved: different phases are now displayed in
different colors.

## ramp_v2.1

* 2019-04-24 09:02:39 +0200  (tag: ramp_v2.1.1)
* 2019-04-19 10:20:39 +0200  (tag: ramp_v2.1)

### Exporting to excel or csv

One can now export the data for all beads and cycles. Simply save a file either
with a '.xlsx' or a '.csv' extension.

## ramp_v2.0

* 2018-11-08 15:11:56 +0100  (tag: ramp_v2.0, tag: cycles_v6.0)

Refactored completely the gui. The latter is architectured as follows:

<table style="border: 1px solid black">
<tr><td>
<table>
  <tr><td style="border-bottom: 1px solid black"><b>Filters</b>: bead quality</td> </tr>
  <tr><td style="border-bottom: 1px solid black"><b>Choice</b>: the type of plots </td></tr>
  <tr><td style="border-bottom: 1px solid black"><b>Table</b>: status summary </td></tr>
  <tr><td style="border-bottom: 1px solid black"><b>Slider & Table</b>: beads clustered by size </td></tr>
  <tr><td style="border-bottom: 1px solid black"><b>Slider</b>: providing the average amount of opened hairpins
  per choice of Z magnet </td></tr>
  <tr><td><b>Table</b>: bead opening amount per Z magnet</td></tr>
</table>
</td>
<td style="border-left: 1px solid black">
<b>Graphic</b>:

* Raw data for a single bead.
* Average behavior for the current bead and an average behavior of all *good* beads,
with their length renormalized to 100.
* Average behavior for the current bead and an average behavior of all *good* beads,
both without length renormalization.

</td>
</tr>
</table>

In particular the amount of opening is very different from the previous
version. Instead of a number of closed beads, it's the median amount of DNA
bases which remain unaccessible because the of beads still being partially
opened. This median amount is over all cycles, irrespective of the beads it
belongs to. Such a computation is hoped to be more robust than the previous one,
especially given the usually low number of cycles available.

Average behaviors are computed for each bead by:

1. subtracting closing hysteresis (phases ... → 3) from the opening hysteresis
   (phases 3 → ...)
2. considering the 25th and 75th percentiles at every available Zmag.

The average behavior for all beads is the median across *good* beads of the
25th and 75th percentile.

## ramp_v1.3

* 2017-03-07 11:30:13 +0100  (tag: ramp_v1.3)

User has now access to a slider (top-right) which allows to specify the ratio
of cycles which the algorithm defines as correct to tag a bead as "good".

Note that the 2 first cycles of the track file are still automatically
discarded (as in pias)


## ramp_v1.2

* 2017-02-22 09:00:37 +0100  (tag: ramp_v1.2)
* 2017-02-09 16:43:47 +0100  (tag: ramp_v1.1.1)
* 2017-01-24 11:11:11 +0100  (tag: ramp_v1.0.1)

* Definition of a good bead has changed:
    For a given bead, if less than 20% of cycles do not open and close has expected
    the bead is tagged good.
    Earlier versions of rampapp discarded a bead as soon
    as one of its cycle misbehaved.
* creates a local server:
    once open the application runs in your webbrowser,
    to open another instance of rampapp, copy the address of rampapp (usually: http://localhost:5006/call_display)
    into a new window
* generates a ramp_discard.csv file for pias
* added a third graph to display the estimated size of each hairpin in the trk files

