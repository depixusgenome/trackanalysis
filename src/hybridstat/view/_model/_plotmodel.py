#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Model for peaksplot"
from   typing                   import Optional, Dict, Any

import numpy as np

from model.plots                import PlotModel, PlotTheme, PlotAttrs, PlotDisplay
from peakcalling.tohairpin      import Distance
from view.colors                import tohex
from view.plots.base            import themed
from tasksequences              import StretchFactor
from utils                      import initdefaults

class PeaksPlotTheme(PlotTheme):
    """
    peaks plot theme
    """
    name            = "hybridstat.peaks.plot"
    figsize         = PlotTheme.defaultfigsize(300, 500)
    xtoplabel       = 'Duration (s)'
    xlabel          = 'Rate (%)'
    fiterror        = "Fit unsuccessful!"
    ntitles         = 4
    count           = PlotAttrs('~blue', '-', 1)
    eventscount     = PlotAttrs(count.color, 'o', 3)
    peakscount      = PlotAttrs(count.color, '△', 15, fill_alpha = 0.5,
                                angle = np.pi/2.)
    referencecount  = PlotAttrs('bisque', 'patch', alpha = 0.5)
    peaksduration   = PlotAttrs('~green', '◇', 15, fill_alpha = 0.5, angle = np.pi/2.)
    pkcolors        = dict(dark  = dict(reference       = 'bisque',
                                        missing         = 'red',
                                        found           = 'black'),
                           basic = dict(reference       = 'bisque',
                                        missing         = 'red',
                                        found           = 'gray'))
    toolbar          = dict(PlotTheme.toolbar)
    toolbar['items'] = 'ypan,ybox_zoom,ywheel_zoom,reset,save,tap'

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class PeaksPlotConfig:
    "PeaksPlotConfig"
    def __init__(self):
        self.name:             str   = "hybridstat.peaks"
        self.estimatedstretch: float = StretchFactor.DNA.value
        self.rescaling:        float = 1.

class PeaksPlotDisplay(PlotDisplay):
    "PeaksPlotDisplay"
    name:            str                   = "hybridstat.peaks"
    distances:       Dict[str, Distance]   = dict()
    peaks:           Dict[str, np.ndarray] = dict()
    baseline:        Optional[float]       = None
    singlestrand:    Optional[float]       = None
    precompute:      int                   = False
    estimatedbias:   float                 = 0.
    constraintspath: Any                   = None
    useparams:       bool                  = False

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

class PeaksPlotModel(PlotModel):
    """
    cleaning plot model
    """
    theme   = PeaksPlotTheme()
    display = PeaksPlotDisplay()
    config  = PeaksPlotConfig()

def createpeaks(mdl, themecolors, vals) -> Dict[str, np.ndarray]:
    "create the peaks ColumnDataSource"
    colors = [tohex(themed(mdl.themename, themecolors)[i])
              for i in ('found', 'missing', 'reference')]

    peaks          = dict(mdl.peaks)
    peaks['color'] = [colors[0]]*len(peaks.get('id', ()))
    if vals is not None and mdl.identification.task is not None and len(mdl.distances):
        for key in mdl.sequences(...):
            peaks[key+'color'] = np.where(np.isfinite(peaks[key+'id']), *colors[:2])
        if mdl.sequencekey+'color' in peaks:
            peaks['color'] = peaks[mdl.sequencekey+'color']
    elif mdl.fittoreference.referencepeaks is not None:
        peaks['color'] = np.where(np.isfinite(peaks['id']), colors[2], colors[0])
    return peaks

def resetrefaxis(mdl, reflabel):
    "sets up the ref axis"
    task = mdl.identification.task
    fit  = getattr(task, 'fit', {}).get(mdl.sequencekey, None)
    if fit is None or len(fit.peaks) == 0:
        return dict(visible = False)
    label = mdl.sequencekey
    if not label:
        label = reflabel
    return dict(ticker     = list(fit.peaks),
                visible    = True,
                axis_label = label)
