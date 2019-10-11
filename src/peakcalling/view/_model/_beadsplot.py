#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"view status"
from dataclasses   import dataclass, field
from typing        import Dict, Any, Set, Tuple

from model.plots   import PlotAttrs
from taskmodel     import RootTask
from tasksequences import StretchFactor

@dataclass
class BeadsScatterPlotStatus:
    """view status"""
    name:     str                      = 'peakcalling.view'
    hairpins: Set[str]                 = field(default_factory = set)
    beads:    Dict[RootTask, Set[int]] = field(default_factory = dict)
    roots:    Set[RootTask]            = field(default_factory = set)

    def masked(self, root = None, bead = None, hairpin = None) -> bool:
        "return whether the item is masked"
        return (
            root in self.roots
            or hairpin in self.hairpins
            or bead    in self.beads.get(root, ())
        )

@dataclass  # pylint: disable=too-many-instance-attributes
class BeadsScatterPlotConfig:
    "Information about the current fovs displayed"
    name:    str             = "peakcalling.view"
    stretch: float           = StretchFactor.DNA.value
    yaxis:   Tuple[str, str] = (
        "postions (base pairs = {:.2f} nm⁻¹)", "positions (base pairs)"
    )
    figargs: Dict[str, Any] = field(default_factory = lambda: dict(
        toolbar_sticky   = False,
        toolbar_location = 'above',
        tools            = ['pan,wheel_zoom,box_zoom,save,reset'],
        plot_width       = 800,
        plot_height      = 400,
        sizing_mode      = 'fixed',
        x_axis_label     = 'bead'
    ))
    events:    PlotAttrs    = field(
        default_factory = lambda: PlotAttrs(
            '', 'rect',
            height      = 10,
            fill_color  = '~gray',
            fill_alpha  = .5,
            line_alpha  = 1.,
            line_width  = 2.,
            line_color  = 'color',
            x           = 'x',
            y           = 'baseposition',
            width       = 'hybridisationrate',
        )
    )
    blockages: PlotAttrs = field(default_factory = lambda: PlotAttrs(
        'color', 'o', 10, x = 'x', y = 'baseposition', fill_alpha = 0., line_alpha = 0.,
    ))
    bindings:  PlotAttrs = field(default_factory = lambda: PlotAttrs(
        'color', 'x', 10, x = 'x', y = 'bindingposition', alpha = .8
    ))
    colors:    Dict[str, str] = field(default_factory = lambda: {
        "truepos":        "lightgreen",
        "falsepos":       "red",
        "falseneg":       "red",
        "baseline":       "dpxblue",
        "< baseline":     "dpxblue",
        "singlestrand":   "dpxblue",
        "> singlestrand": "dpxblue",
        "":               "lightgreen"
    })
    order:    Dict[str, int] = field(default_factory = lambda: {
        j: i
        for i, j in enumerate((
            "baseline", "< baseline", "singlestrand", "> singlestrand",
            "", "truepos", "falsepos", "falseneg"
        ))
    })
