#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All things needed to create and start an application"
import sys
import glob
from   pathlib import Path

paths = (str(Path(__file__).parent.parent.resolve()),)+tuple(glob.glob("*.pyz"))
for path in paths:
    if path not in sys.path:
        sys.path.append(path)

import utils.logconfig # make sure logging is configured
from .launcher  import Defaults, ToolBar, BeadToolBar, setup
