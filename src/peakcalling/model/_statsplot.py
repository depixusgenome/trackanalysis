#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"stats plot status"
from dataclasses    import dataclass, field
from typing         import Dict, List, Any, Tuple, Union, Optional
import numpy as np

from model.plots    import PlotAttrs, defaultfigsize
from taskmodel      import RootTask
from view.threaded  import DisplayModel
from cleaning.names import NAMES as _ExceptionNames
from ._columns      import INVISIBLE, COLS
from ._beadsplot    import BeadsScatterPlotStatus, BasePlotConfig
from ._control      import TasksModelController

YAxisNorm      = Optional[Tuple[str, List[str]]]
NAME:      str = 'peakcalling.view.stats'

@dataclass
class FoVStatsPlotStatus(BeadsScatterPlotStatus):
    "Information about the current fovs displayed"
    name:      str                 = NAME
    tracktag:  Dict[RootTask, str] = field(default_factory = dict)
    reference: Optional[RootTask]  = None

@dataclass(eq = True)
class AxisConfig:
    "info on x axis parameter"
    name:        str
    sortbyvalue: bool = True
    norm:        bool = True

@dataclass(eq = True)
class BinnedZ:
    "allows binning z values"
    width:     float = .1
    step:      float = .1
    precision: int   = 2

    def reset(self, default = .1):
        "updates self to something meaningful"
        if self.width <= 0.:
            self.width = default

        if (
                self.width == self.step
                and np.abs(np.round(self.width, self.precision) - self.width) < 1e-5
        ):
            return

        self.step      = self.width
        self.precision = 0
        while np.abs(np.round(self.width, self.precision) - self.width) >= 1e-5:
            self.precision += 1
        self.width = self.step = np.round(self.width, self.precision)

@dataclass  # pylint: disable=too-many-instance-attributes
class FoVStatsPlotConfig(BasePlotConfig):
    "Information about the current fovs displayed"
    name:      str                = NAME
    linear:    bool               = True
    refagg:    str                = 'median'
    yaxisnorm: YAxisNorm          = field(default_factory = lambda: ("status", ["", "truepos"]))
    binnedz:   BinnedZ            = field(default_factory = BinnedZ)
    binnedbp:  BinnedZ            = field(default_factory = lambda: BinnedZ(10, 10, 0))
    xinfo:     List[AxisConfig]   = field(
        default_factory = lambda: [AxisConfig('track'), AxisConfig('beadstatus')]
    )
    yaxis:     str                = 'bead'
    xaxistag:  Dict[str, str]     = field(
        default_factory = lambda: {
            i.key: str(i.label) for i in COLS if (i.axis == 'x') and i.label
        }
    )
    yaxistag: Dict[str, str]      = field(
        default_factory = lambda: {
            i.key: str(i.label) for i in COLS if (i.axis == 'y') and i.label
        }
    )
    orientationtag: Dict[str, str] = field(
        default_factory = lambda: {"+": "+", "-": INVISIBLE+"-", "": INVISIBLE*2+'?'}
    )

    uselabelcolors:   bool           = True
    defaultcolors:    str            = 'Blues'
    orientationcolor: Dict[str, str] = field(
        default_factory = lambda: {"+": "lightgreen", "-": "dpxblue"}
    )
    statuscolor: Dict[str, str] = field(
        default_factory = lambda: {
            "< baseline":     f"dpxblue",
            "baseline":       f"dpxblue",
            "truepos":        f"lightgreen",
            "falseneg":       f"red",
            "falsepos":       f"red",
            "":               f"green",
            "singlestrand":   f"dpxblue",
            "> singlestrand": f"dpxblue",
        }
    )
    beadstatuscolor: Dict[str, str] = field(
        default_factory = lambda: {
            "ok":       "lightgreen",
            **dict.fromkeys(("empty", "bug", "unknown"), "red"),
            **dict.fromkeys(_ExceptionNames.keys(), "red")
        }
    )
    spread:   float           = 1.5
    toplabel: Tuple[str, str] = ('Bead count', 'Bead / Blockage count')
    toptick:  Tuple[str, str] = ('{}', '{}/{}')
    figargs: Dict[str, Any] = field(default_factory = lambda: dict(
        toolbar_sticky   = False,
        toolbar_location = 'above',
        tools            = ['pan,wheel_zoom,box_zoom,save,reset,hover'],
        plot_width       = 900,
        plot_height      = 400,
        sizing_mode      = defaultfigsize()[-1],
    ))
    tooltipcolumns: List[Tuple[str,str]] = field(default_factory = lambda: [
        ("x", "@xv"), ("y", "@yv"),
    ])
    box:      PlotAttrs       = field(
        default_factory = lambda: PlotAttrs(
            '', 'rect',
            fill_color  = 'color',
            line_color  = 'color',
            x           = 'x',
            y           = f'boxcenter',
            width       = .9,
            height      = f'boxheight',
        )
    )
    vertices: PlotAttrs = field(
        default_factory = lambda: PlotAttrs(
            '', 'segment',
            line_color  = 'dpxblue',
            line_width  = 2,
            x0          = 'x',
            x1          = 'x',
            y0          = f'bottom',
            y1          = f'top',
        )
    )
    median: PlotAttrs = field(
        default_factory = lambda: PlotAttrs(
            '', 'rect',
            fill_color  = 'black',
            line_color  = 'black',
            x           = 'x',
            y           = 'median',
            height      = .00001,
            line_width  = 1,
            width       = .9,
        )
    )
    bars:   PlotAttrs = field(
        default_factory = lambda: PlotAttrs(
            '', 'rect',
            fill_color  = 'dpxblue',
            line_color  = 'dpxblue',
            x           = 'x',
            height      = .00001,
            line_width  = 3,
            width       = .5,
        )
    )
    points: PlotAttrs = field(
        default_factory = lambda: PlotAttrs(
            '~gray', 'circle',
            x           = 'x',
            y           = 'y',
            size        = 10
        )
    )

    @property
    def xaxis(self) -> List[str]:
        "return x-axis names"
        return [i.name for i in self.xinfo]

    def getxaxisinfo(self, attr:str, xaxis: List[Union[str, AxisConfig]]) -> list:
        "x axis info"
        vals = {getattr(j, 'name', j): i for i, j  in enumerate(xaxis)}
        return sorted(vals[i.name] for i in self.xinfo if i.name in vals and getattr(i, attr))

class FoVStatsPlotModel(DisplayModel[FoVStatsPlotStatus, FoVStatsPlotConfig]):
    "model for display the FoVs"
    tasks: TasksModelController

    def __init__(self, **_):
        super().__init__()
        self.tasks = TasksModelController()

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        super().swapmodels(ctrl)
        self.tasks.swapmodels(ctrl)
