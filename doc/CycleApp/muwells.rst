.. include:: ../utils.rst

================
Micro-Wells Data
================

Currently, the micro-wells data comes in two files:

* a track (``.trk``) file created by the ``picotwist``,
* a text file (``.txt``) created by the lock-in amplifier. Its format is :

  1. 4 lines starting by '%'. One of which main contain the hairpin size coded as ``% sequence: 1200``.
  2. A fith line which must be: ``% Time(s), Amplitude (V)``.
  3. lines containing the time, a semi-colon and the voltage

Both files are unsynchronized. This is corrected upon loading the text file.

Synchronization
===============

The synchronization is done by:

1. extracting the opening of the molecule which occurs in phase 2 from the data in the text file,
2. extracting the framerate from the same file and correcting the data from the track file accordingly.
3. matching the cycle durations from the track file to the cycle durations
   estimated using the opening time found in the text file.
4. extracting a scale in µV by looking at the median dynamic range covered by
   the data in the text file in each cycle.
5. correcting z-axis dependant parameters in the workflow according to this µV
   scale and the expected hairpin size. This size is 1073 bases per default
   (Hairpin HP5).

Differences with the optical systems
====================================

The main difference is the hardware low-pass filter applied to the data and the
frame rate. This low-pass filter has a cutoff value which can be set within a
range from 1ms to 100ms or more. It's effect is always to remove noise at
high-frequencies. Anything above 1/30Hz will affect the current high-frequency
noise estimator |NOISE|. As the latter is used throughout the processing
pipeline as a calibration factor. This can have a profound effect on the data
processing output. For now, there are no automated way of measuring the effect
and correcting for it.

As a result, in the cleaning tab, one might be required to change the
parameters used, in particular, the |pingpong| test can under-estimate the
high-frequency noise, resulting in an over-estimation of the low-frequency
noise it tries to detect. One might need to increase the |pingpong| settings
available on the advanced menu.

In the peaks tabs, the same effect might result in too low a smearing the peak
data in the histograms. On may wish to raise the setting in the advanced menu.
