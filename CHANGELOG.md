# tag cycles_v4.4.1
## Tagger: Pol d'Avezac <pol.davezac@depixus.com>

### Cleaning & Xlsx reports

* Beads responsible for an automated warning are systematically discarded from
  xlsx reports. The only way to have them in the reports is to update the
  filters in the *Cleaning* tab.

### Bugs

* Saving an xlsx file from a tab other than *Cycles* or *Peaks* could result in
  a crash.
* If beads responsible for an automated warning (in the messages tab) were not
  discarded, saving an xlxs file resulted in a crash


# tag cycles_v4.4
## Tagger: Pol d'Avezac <pol.davezac@depixus.com>

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

# tag cycles_v4.3
## Tagger: Pol d'Avezac <pol.davezac@depixus.com>

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

# tag cycles_v4.2
## Tagger: Pol d'Avezac <pol.davezac@depixus.com>

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

# tag cycles_v4.1
## Tagger: Pol d'Avezac <pol.davezac@depixus.com>

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

# tag cycles_v4.0
## Tagger: Pol d'Avezac <pol.davezac@depixus.com>

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

# tag cycles_v2.0
## Tagger: Pol d'Avezac <pol.davezac@depixus.com>
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

# tag cycles_v1.0
## Tagger: Pol d'Avezac <pol.davezac@depixus.com>
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

# tag ramp_v1.3
## Tagger: David Salthouse <david.salthouse@depixus.com>

User has now access to a slider (top-right) which allows to specify the ratio
of cycles which the algorithm defines as correct to tag a bead as "good".

Note that the 2 first cycles of the track file are still automatically
discarded (as in pias)


# tag ramp_v1.2
## Tagger: David Salthouse <david.salthouse@depixus.com>

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
