<table>
<tr> <td>CLANG <a href=/viewType.html?buildTypeId=BuildClang&guest=1">
<img src="http://jupyter.depixus.org:8111/app/rest/builds/buildType:BuildClang/statusIcon"/>
</a></td>

<td>GCC <a href="http://jupyter.depixus.org:8111/viewType.html?buildTypeId=Trackanalysis_Build&guest=1">
<img src="http://jupyter.depixus.org:8111/app/rest/builds/buildType:Trackanalysis_Build/statusIcon"/>
</a></td>

<td>Unit tests <a href="http://jupyter.depixus.org:8111/viewType.html?buildTypeId=Trackanalysis_Test&guest=1">
<img src="http://jupyter.depixus.org:8111/app/rest/builds/buildType:Trackanalysis_Test/statusIcon"/>
</a></td>

<td>Integration tests <a href="http://jupyter.depixus.org:8111/viewType.html?buildTypeId=Trackanalysis_IntegrationTest&guest=1">
<img src="http://jupyter.depixus.org:8111/app/rest/builds/buildType:Trackanalysis_IntegrationTest/statusIcon"/>
</a></td>
</table>

For continuous integration, please visit [TeamCity tests](http://jupyter.depixus.com:8111/project/DAQClient?branch=&buildTypeTab=overview)

## Installation

Obtaining the code is done through git
```shell
# copy the directory to your computer: needed only once
git clone https:://gitlab.picoseq.org/analysis/trackanalysis.git
cd trackanalysis

# get the latest code
git pull

# update the submodules
git submodule update --init --recursive
```

The python/cpp/javascript environment is managed through the *anaconda* software.
Install either *miniconda* or *anaconda* then run an *anaconda* shell
(any will do when using linux). We then rely on the *waf* utility to setup the environment
and build or install a new distribution.

```shell
# setup the environment: when working on a branch the environment name is that
# of the branch. Otherwise, the name is daqclient. This is needed as often
# as the repository's environment changes
python waf setup

# Configure the waf compiler, needed every time the environment changes and before
# running an 'install' command. One needs add '--fulldist' to get a full installation.
# Otherwise only a patch is created
python waf configure

# Compile the files: all necessary files are created in the 'build' directory. This
# is needed every time the code changes
python waf build

# Run the tests !!!
python waf test --alltests --pv

# To create a distribution or a patch, the following will transfer required files
# in the build/patch_[tagname] or buil/[tagname] directory where [tagname] is the 
# current git description of the repository. When delivery code to third parties,
# this description should correspond to the last tag and have neither hash number
# nor '+' (i.e dirty) at the end of the name.
python waf install
```

## Installing on windows

Required by windows for compiling the C++ is Visual Studio c++. It's been tested
to work on MSVC community edtion 2019. The following options were checked
(a shorter list *might also work as well*):

* Python: everything can be unchecked
* C++:

  * MSVC v142
  * Windows SDK
  * C++ profile tools
  * C++ make tools
  * C++ ATL
  * C++ MFC
  * C++/CLI
  * C++ modules
  * MSVC v140

## Known problems

All known problems are dealt with automatically inside the waf script, unless it's
an environment update. Depending on the python package being updated, these may not
function correctly. The simple solution is to remove the environment prior to running
the setup again. To the best of our knowledge, this is an issue only for pylint/astroid
updates 

```shell
conda remove -n trackanalysis --yes
python waf setup
```

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
