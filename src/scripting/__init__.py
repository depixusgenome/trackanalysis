#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import,wildcard-import,ungrouped-imports
"""
Used for scripting: something similar to matplotlib's pyplot.
"""
import shutil
import sys
from pathlib         import Path
from utils.scripting import run
TUTORIAL = f"""
The data can be accessed with 2 objects:

1. `Track` can read the data in the track file and provide access to beads
and cycles. The latter can be accessed using `Track.beads` or `Track.cycles`
amongst other ways. In jupyter, these will be displayed automatically using
*holoviews* objects.

2. `TracksDict` can read the data from multiple track files. In jupyter its
displays are adapted to multiple files and can be much richer.

3. `Tasks` provides means for transforming the data, for example into `pandas.DataFrame`
objects. Detailed information is available in jupyter by simply typing `Tasks.cleaning`
where `cleaning` is only one amongst other transformations.

For each of these objects, a detailed documentation is available. Start with
`Track?`, `Track.cycles?` or for example.
"""
run(locals(),
    direct  = ('sequences', 'anastore', 'taskstore'),
    star    = ("signalfilter", "utils.datadump", "utils.scripting",
               *(f"{i}.__scripting__" for i in ("taskmodel", "taskapp", "data", "cleaning",
                                                "eventdetection", "peakfinding",
                                                "peakcalling"))),
    jupyter = (f"{i}.__scripting__.holoviewing"
               for i in ("data", "cleaning", "eventdetection", "peakfinding", "peakcalling",
                         "qualitycontrol", "ramp", "taskmodel")))


if Path("Tutorial.ipynb").exists():
    TUTORIAL += """
You can access a full tutorial [here](Tutorial.ipynb) and [here](aligningexperiments.ipynb)
"""
else:
    TUTORIAL += f"""
A jupyter tutorial is available in jupyter. Do:

```python
shutil.copyfile("{__file__[:__file__.rfind("/")+1]+"Tutorial.ipynb"}", "Tutorial.ipynb")
shutil.copyfile("{__file__[:__file__.rfind("/")+1]+"/aligningexperiments.ipynb"}",
                "aligningexperiments.ipynb")
```

and follow the links:
* [Jupyter tutorial](Tutorial.ipynb)
* [Aligning experiments](aligningexperiments.ipynb)
"""

if __file__[:__file__.rfind("/")] not in sys.path:
    sys.path.append(__file__[:__file__.rfind("/")])
