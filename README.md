# Project Goals

* User-friendly, platform agnostic data analysis tools.
* Batch *and* GUI modes must both function.

# Architecture

The global architecture principle is *Model-View-Controller*.

## The model

The model is separated into the following elements:

* GUI Settings: user preferences, last opened track .... This should be saved in its own user-dependant file.
* Data: bead tracks and such. The data is considered read-only, produced by the acquisition software.
  For batching to work, this must remain separate from tasks.
* Tasks: configuration information for data-treatment and data-analysis items.
  For batching to work, this must remain separate from data. For the same reason,
  implementation is left to the controller (see src/control/processor/). It might
  change depending on whether we are working in batch or gui mode.
* View-specific settings: data-dependant information such as plot ranges, colors,
  ... which can be changed by the user in gui mode. This information can be saved
  together with tasks but must not affect the batch mode.

## The Task Controller

It contains:

* A list of tasks.
* A list of pairs (processor, cache), one per task. The cache can be left empty.

Processors work on *lazy* *directed acyclic graphs*. The graph nodes are created
first, before execution. The latter is not always performed:
* Using iterators (i.e. directed acyclic aspect) limits the use of resources.
* Creating nodes without executing them allows for parallelizing.
* Allows selecting only part of the graph for execution and display in the gui.

The cache is here to prevent too many re-computations.

## Warnings for the developper:

Controllers are considered mixin classes: An application controller derives from
all controllers used by it. As such they must have distinctive names for their methods.

This is also true for views.

Undos are *always* implemented: see src/view/undo.py

# Ramp Treatment

TODO:

* Find bead magnetization strength.

* Find structural bindings.

# Data Treatment

Given a set of beads, one needs to:

* Remove drifts: noise which is correlated either between beads in a cycle or between
  cycles in a bead. After this stage, the graphs should be a sequence of straight lines.

* Reset cycle zero-position: drifts result in the loss of an absolute position between cycles.
  Thus they need to be shifted to a common zero position.

    * One option is to use the *pull* phase (3) as this has the smallest
      brownian motion. In such a case, the stretch must not vary from cycle to
      cycle.

    * Flat events in the *measure* phase (5) should provide us with more points 
    on which to fit cycles from one to the next. This is valid as long as there
    are enough events per cycle.

* Measure flat events size and position:

    * Structural events should be discarded.

    * The fork can de-hybridizes during an event. any flat stretch occurring
      higher than a previous event belongs to the latter.

* Identify beads: in some protocols, the same hairpins appear on multiple beads.
  The beads must be clustered and their stretch and bias determined.
