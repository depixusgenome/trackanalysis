# Project Goals

* User-friendly, platform agnostic data analysis tools.
* Scripting, batch *and* GUI modes must both function. Computations whatever the
mode should be a single piece of code.
* The documentation should be in the code. The class and function documentation
is user-oriented. Comments are for the developpers. 

# Installing

The first step is to install boost libraries, either using the linux distribution's package manager or installing them manually.

Clone the git repository and it's submodules, then set up the 
environment and build:

```shell
git clone http:\\GIT-REPO
git submodule update --init --recursive

python3 waf setup [-n myenv]
[conda activate myenv]

python3 waf configure [--boost-includes=BOOST_INCLUDEPATH --boost-libs=BOOST_LIBSPATH]

python3 waf build
```

Items in between [] are optional or specific to windows:

* [-n myenv] is optional. [conda activate myenv] is mandatory if and
  only if the [-n myenv] option was used.

* [--boost ... ] are mandatory only if BOOST was installed manually.

The *configure* and *setup* steps are every time new dependencies
are added. The *build* step is required any time sources are
changed.

## Known problems

### As of 2018-01-01

#### pyembed error

The default python installed by conda might not be compatible with compiling
native code (*pybind11*) modules. The solution is to look for and install a
version of python as follows:

```shell
conda search -f python -c conda-forge
```

It spits out a list of values such as:

    ...
    python                     3.6.3                hefd0734_2  defaults       
    python                     3.6.4                         0  conda-forge    
    python                     3.6.4                hc3d631a_0  defaults       
    python                     3.6.4                hc3d631a_1  defaults 

The *undocumented* tags in the 3rd column are the relevant piece of information.
Choose a tag from *conda-forge* (4th column). The tag always seems to be an integer.
Its value doesn't seem to matter.

# Architecture

The global architecture principle is *Model-View-Controller*.

## Documentation

Public classes and functions must provide a *user-oriented* description. Comments
are for developpers only. The format is markdown. It should include:

    1. A one liner description.
    2. A detailed explanation which can be divided into sections.
    3. For classes: and `# Attributes` section containing a list of the
    instance's public attributes.

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

## Scripting mode

A scripting mode is available. The code is available in `__scripting__` sub-modules.
It should provide easier means for accessing the data, extracting information and
displaying results. **This is just sugar**. Any real computations should be in the
parent modules.

Displays rely on *holoviews* which can only be used within *jupyter*. This is why
displays are coded into `__scripting__.holoviewing` sub-modules.

To invoke the scripting mode, add `from scripting import *` to the start of your
script or jupyter file.

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
