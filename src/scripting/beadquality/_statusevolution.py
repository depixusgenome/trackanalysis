#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""
from   typing    import Union, List, cast

from   bokeh.models  import HoverTool, FactorRange, CategoricalAxis
import pandas    as pd
import holoviews as hv # pylint: disable=import-error

from   utils         import initdefaults
from   ._trackqc     import TrackQC

class StatusEvolution:
    """
    Display the evolution of beads in the 3 categories: 'ok', 'fixed' and 'missing'.
    """
    params    = 'ok', 'error', 'fixed', 'missing'
    colors    = 'green', 'orange',  'blue', 'red'
    tooltips  = [("(date, track)", "(@date, @track)"),
                 *((f"# {i}", f"@{i}") for i in params),
                 ("# cycles", "@cyclecount")]
    xlabel    = 'date'
    ylabel    = '% beads (total {total})'
    title     = "Evolution of the bead status as function of time"
    ptsstyle  = {'marker': 'o', 'size': 5}
    styleopts = {'show_grid': True, 'xrotation': 45}

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @staticmethod
    def dataframe(trackqc: Union[pd.DataFrame, TrackQC]) -> hv.Overlay:
        "The dataframe used for the displays"
        frame         = trackqc.table.reset_index()
        frame['date'] = frame.modification.apply(lambda d: f'd{d.day}-{d.hour}h{d.minute}m')
        return frame

    def display(self, trackqc: Union[pd.DataFrame, TrackQC])->hv.Overlay:
        "Scatter plot showing the evolution of the nb of missing, fixed and no-errors beads."
        frame = self.dataframe(trackqc)
        total = len(trackqc.status.index)
        for i in self.params:
            if i in frame:
                frame[i] *= 100/total
        hover                  = HoverTool(tooltips = self.tooltips)
        crvs: List[hv.Element] = []
        for tpe, opts in zip((hv.Points, hv.Curve), (self.ptsstyle, {})):
            opts = {'tools': [hover], **cast(dict, opts), **cast(dict, self.styleopts)}
            crvs.extend(
                tpe(frame, kdims = ['date', i], label = i).options(color = j, **opts)
                for i, j in zip(self.params, self.colors)
                if i in frame
            )

        def _newaxis(plot, _):
            plot.state.extra_x_ranges = {"track": FactorRange(*frame.track.values)}
            plot.state.add_layout(CategoricalAxis(x_range_name="track"), 'above')

        return (hv.Overlay(crvs)
                .redim.range(y = (0,100))
                .redim.label(x = self.xlabel, ok = self.ylabel.format(total = int(total)))
                .options(finalize_hooks=[_newaxis])
                .clone(label=self.title)
               )

def displaystatusevolution(trackqc: Union[pd.DataFrame, TrackQC], **kwa)->hv.Overlay:
    "Scatter plot showing the evolution of the nb of missing, fixed and no-errors beads."
    return StatusEvolution(**kwa).display(trackqc)

__all__ = ['displaystatusevolution']
