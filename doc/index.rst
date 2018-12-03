.. CycleApp documentation master file, created by
   sphinx-quickstart on Wed Nov 28 09:02:29 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. include:: utils.rst

Welcome to CycleApp's documentation!
====================================

What is |CycleApp| for ?
---------------------------------

This software is for *offline* analyses of hybridization data. By this we mean
data collected from |SIMDEQ| instruments over one field of view and a
number of cycles. Theses concept of beads and cycles are central to the
software. Its main goal is to aggregate information from all cycles into
characteristics - position, rates and durations - for each blocking position in
each bead individually. This information can be saved to an excel file for
further studies.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   gettingstarted
   fov
   qc
   cleaning
   cycles
   peaks
