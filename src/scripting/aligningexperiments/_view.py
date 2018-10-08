#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scripts for aligning beads & tracks
"""
from   typing       import cast
import pandas       as     pd
import numpy        as     np
import holoviews    as     hv
from   bokeh.models                         import (LinearAxis,FuncTickFormatter,
                                                    FixedTicker)

from   model.__scripting__                  import Tasks
from   peakfinding.processor                import PeaksDict, PeakSelectorTask
from   peakfinding.__scripting__            import Detailed
from   utils.decoration                     import extend
from   ._identification                     import FalsePositivesIdentifier
from   ._computations                       import (PeaksAlignmentConfig,
                                                    getreference, HPPositions)

def showresolutions(data, *keys: str, rng = (0., 8.)):
    "show resolutions"
    def _fcn(key):
        info = data[key].assign(resolution = data[key].resolution*1e3)
        return hv.BoxWhisker(info, ['trackcount', 'bead'],  'resolution')

    out = (hv.DynamicMap(_fcn, kdims = ['data'])
           .redim.values(data = list(keys))
           .redim.range(resolution = rng))

    return out if len(keys) != 1 else out[keys[0]]

def showmissingpertrack(data, percentage = False):
    "show missing per track"
    if percentage:
        return hv.Bars(data.delta.isna().sum(level=0)/data.delta.count(level = 0))
    return hv.Bars(data.delta.isna().sum(level=0))

def showidentifiedpeaks(data, # pylint: disable=too-many-arguments
                        missingvalue = 20,
                        dynmap       = False,
                        adjoint      = True,
                        width        = 600,
                        height       = 100):
    """
    Show expected peaks in a heatmap
    """
    # pylint: disable=too-many-locals
    if dynmap:
        fcn = lambda x: showidentifiedpeaks(data.loc[[x]], missingvalue, None, False)
        return (hv.DynamicMap(fcn, kdims = ['track'])
                .redim.values(track = sorted(data.index.levels[0].unique())))
    vals = (data
            .reset_index(level = [0, 2])
            .loc[list(data.groupby(level =1).hfsigma.mean().sort_values().index)]
            .sort_values(['reference'])
            .assign(dist = lambda x: np.abs(x.delta)))

    if len(vals.track.unique()) > 1:
        ref          = 'ref'
        vals['ref']  = vals.reference.astype(str)+" "+vals.track
    else:
        ref          = 'reference'

    inds = vals.delta.isna().sum(level=0).sort_values().index
    vals = pd.concat([vals.loc[[i]] for i in inds])

    opts = dict(xrotation=90, width=width)
    hmap = hv.HeatMap(vals.fillna(missingvalue), [ref, "bead"], "dist")
    if not adjoint:
        opts.pop('width')
        return hmap(plot = opts)

    beads  = (hv.Bars(vals.delta.isna().sum(level=0)[::-1])
              .redim(x="bead", y="missbeads"))
    pos    = (hv.Bars(vals.reset_index().set_index(ref)
                      .delta.isna().sum(level=0))
              .redim(x=ref, y="misspos"))

    return (hmap(plot = opts)
            << beads(plot=dict(width=height, yaxis = None))
            << pos  (plot=dict(height=height, width=width, xaxis = None)))

def addsequenceticks(plot, seq, position):
    "add sequence ticks and possibly a new axis"
    if isinstance(seq, HPPositions):
        code  = seq.seq.upper().replace(seq.target.upper(), seq.target.lower())
        ticks = list(range(len(seq.seq)))
    else:
        code  = seq
        ticks = list(range(len(seq)))

    def _set(axis):
        axis.formatter = FuncTickFormatter(code= f'return "{code}"[tick]')
        axis.ticker    = FixedTicker(ticks = ticks)

    if position in ('xaxis', 'yaxis'):
        opts = lambda x, y: _set(getattr(x.state, position))

    else:
        rng = 'x_range' if position in ('above', 'bottom') else 'y_range'
        def _add(plot, _):
            plot.state.extra_x_ranges = {"seq":  getattr(plot.state, rng)}
            linaxis = LinearAxis(**{'axis_label' : "sequence", f'{rng}_name': 'sequence'})
            _set(linaxis)
            plot.state.add_layout(linaxis, position)
        opts = _add
    return plot(plot=dict(finalize_hooks=[opts]))

def showfalsepositives(itms, rng, precision = 1, scatter = False, **kwa):
    "display false positives"
    cls    = FalsePositivesIdentifier
    fpos   = cls.falsepositives(itms)
    tracks = sorted(fpos.track.unique())
    dico   = PeaksDict(config = cast(PeakSelectorTask, Tasks.peakselector(**kwa)))
    def _showfp(track):
        data  = fpos[fpos.track == track]
        beads = data.bead.unique()
        dtl   = cls.detailed(dico.config, data, precision = precision)
        disp  = getattr(Detailed(dico, dtl), 'display')(zero = False).display()
        crv   = hv.Curve((list(rng), [3, 3]))(style=dict(linewidth=20, alpha=.5))
        ovr   = hv.Overlay(list(disp)+[crv])
        if scatter:
            scatt = (hv.Scatter(data, 'bead', 'z')(plot=dict(jitter=.8))
                     *hv.Scatter((np.concatenate([beads]*2),
                                  [rng[0]]*len(beads)+[rng[0]]*len(beads))))
            return (ovr+scatt).cols(1)
        return ovr
    return hv.DynamicMap(_showfp, kdims = ['track']).redim.values(track = tracks)

@extend(PeaksAlignmentConfig)
class PeaksAlignmentConfigMixin:
    """
    config for aligning peaks
    """
    def showone(self,   # pylint: disable=too-many-arguments,too-many-locals
                data,
                ref        = None,
                discarded  = None,
                masks      = None,
                align      = True,
                refpos     = None,
                pivot      = 'max',
                trackorder = 'modification',
                **seqs):
        "display the data"
        if not isinstance(data, pd.DataFrame):
            data = self.peaks(data)

        if align:
            data = self(data, ref, # pylint: disable=not-callable
                        discarded=discarded, masks=masks, pivot=pivot, refpos=refpos)
            ref  = None

        data = data.sort_values(['bead', trackorder, 'peakposition', 'avg'])
        if ref is None:
            ref  = 'identity' if 'identity' in data.columns else 'track'

        cols = ['resolution', 'hybridisationrate', 'averageduration']
        dim  = hv.Dimension("z", label = "base pairs")
        args = ref, ['avg']+cols[1:]
        opts = dict(plot  = dict(jitter = .75), style = dict(alpha  = .2))
        if 'reference' in data:
            isna = data.reference.isna()
            out  = (hv.Scatter(data[~isna], *args, label = 'events')(**opts).redim(avg = dim)
                    *hv.Scatter(data[isna], *args,
                                label = 'unknown events')(**opts).redim(avg = dim))
        else:
            out  = hv.Scatter(data, *args, label = 'events')(**opts).redim(avg = dim)

        out  *= (hv.Scatter(data, ref, ['peakposition']+cols[:1], label = 'peaks')
                 (plot  = dict(size_index     = 'resolution',
                               scaling_factor = 15000),
                  style = dict(alpha = .01, line_alpha=.1))
                 ).redim(**{cols[0]: dim})

        args = dict(style = dict(color = 'gray', alpha = .5, size = 5), group = 'ref')
        for i, j in seqs.items():
            out = self.showhpin(data, j, ref, label = i, **args)*out

        return out if self.hpalign else out

    @staticmethod
    def showhpin(data, positions, ref = None, plot = None, style = None, **args):
        """
        display hairpin positions
        """
        if ref is None:
            ref  = 'identity' if 'identity' in data.columns else 'track'
        xvals = list(set(data[ref].unique()))
        out   = hv.Scatter((xvals * len(positions),
                            np.repeat(positions, len(xvals))), **args)
        return out(plot  = plot  if plot else dict(),
                   style = style if style else dict())

    def show(self, data, # pylint: disable=too-many-arguments,too-many-locals
             keys       = (),
             beads      = (),
             trackorder = 'trackorder',
             align      = True,
             ref        = None) -> hv.DynamicMap:
        "return a dynamic map"
        def _fcn(key, bead):
            info = data if isinstance(data, pd.DataFrame) else data[key]
            return self.showone(info[info.bead == bead], ref,
                                trackorder = trackorder,
                                align      = align,
                                pivot      = self.pivots.get(bead, self.defaultpivot),
                                masks      = self.masks.get(bead, None),
                                refpos     = self.refpos.get(bead, None))

        if isinstance(data, pd.DataFrame):
            _f1 = lambda x: _fcn(None, x)
            if len(beads) == 0:
                beads = sorted(data.bead.unique())
            out = (hv.DynamicMap(_f1, kdims = ['bead']) .redim.values(bead = list(beads)))
        elif len(keys) == 1:
            _f2 = lambda x: _fcn(keys[0], x)
            out = (hv.DynamicMap(_f2, kdims = ['bead']) .redim.values(bead = list(beads)))
        elif len(beads) == 1:
            _f3 = lambda x: _fcn(x, beads[0])
            out = (hv.DynamicMap(_f3, kdims = ['data']) .redim.values(data = list(keys)))
        else:
            out = (hv.DynamicMap(_fcn, kdims = ['data', 'bead'])
                   .redim.values(data = list(keys), bead = list(beads)))

        if self.hpin:              # type: ignore
            pos    = self.hpin.pos # type: ignore
            tracks = list(pos.track.unique())
            rpos   = pos[pos.track == getreference(tracks)].position.values
            out    = (out
                      *hv.Scatter(pos[pos.target & pos.strand], 'track', 'position')
                      (style ={'color':'green'})
                      *hv.Scatter(pos[pos.target & ~pos.strand], 'track', 'position')
                      (style ={'color':'red'})
                      *hv.Scatter((np.repeat(tracks, rpos.size),
                                   np.concatenate([rpos]*len(tracks))))
                      (style ={'color':'gray'})
                     )
        return out
