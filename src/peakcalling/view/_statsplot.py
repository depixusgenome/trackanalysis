#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows FoV stats"
from   abc                     import abstractmethod
from   typing                  import (
    Dict, List, Tuple, Generator, ClassVar, Set, FrozenSet
)
import re

import pandas as pd
import numpy  as np

from   bokeh                   import layouts
from   bokeh.models            import (
    ColumnDataSource, FactorRange, CategoricalAxis, DataRange1d
)
from   bokeh.plotting          import figure, Figure

from   data.trackops           import trackname
from   view.colors             import tohex
from   view.threaded           import ThreadedDisplay
from   taskcontrol.processor   import ProcessorException
from   ._model                 import FoVStatsPlotModel, INVISIBLE, COLS
from   ._widgets               import JobsStatusBar, JobsHairpinSelect, PeakcallingPlotWidget
from   ._threader              import BasePlotter, PlotThreader

_DATA  = Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]
_XCOLS = frozenset({i.key for i in COLS if i.axis == 'x' and i.raw})
_YCOLS = frozenset({i.key for i in COLS if i.axis == 'y' and i.raw})
_IDS   = ['trackid', 'bead']

def boxbottom(val):
    "the 1st quartile"
    return np.nanpercentile(val, 25)

def boxtop(val):
    "the 3rd quartile"
    return np.nanpercentile(val, 75)


@PlotThreader.setup
class FoVStatsPlot(  # pylint: disable=too-many-instance-attributes
        ThreadedDisplay[FoVStatsPlotModel]
):
    "display the current bead"
    _fig:      Figure
    _topaxis:  CategoricalAxis
    _stats:    ColumnDataSource
    _points:   ColumnDataSource
    _defaults: Dict[str, list]
    _DATAYCOLS: ClassVar[FrozenSet[str]] = frozenset({
        'boxcenter', 'boxheight', 'median', 'bottom', 'top'
    })
    _DATAXCOLS: ClassVar[FrozenSet[str]] = frozenset({'x', 'beadcount'})

    def __init__(self, widgets = True, **_):
        super().__init__(**_)
        self._widgets  = (
            (JobsStatusBar(), JobsHairpinSelect(), PeakcallingPlotWidget()) if widgets else
            ()
        )
        self._defaults = dict(
            {i: np.array(['']) for i in  _XCOLS | self._DATAXCOLS},
            **{f'{j}': np.array([0.]) for j in self._DATAYCOLS},
        )
        self._defaults['color'] = ["green"]

    _reset = None   # added in _Threader.setup

    def createplot(self) -> BasePlotter:
        "runs the display"
        procs = self._model.tasks.processors
        if getattr(_BeadStatusPlot, '_NAME') in self._model.theme.xaxis:
            return _BeadStatusPlot(self, procs)
        return (_HairpinPlot if BasePlotter.ishairpin(procs) else _PeaksPlot)(self, procs)

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        super().swapmodels(ctrl)
        for i in self._widgets:
            if hasattr(i, 'swapmodels'):
                i.swapmodels(ctrl)

    def observe(self, ctrl):
        """observe the controller"""
        for i in self._widgets:
            if hasattr(i, 'observe'):
                i.observe(ctrl, self._model.tasks)

        @ctrl.display.observe(self._model.display)
        def _ontracktags(old, **_):
            if 'tracktag' in old:
                getattr(self, '_threader').renew(ctrl, 'reset', True)

        theme = frozenset({
            'xinfo', 'yaxis', 'uselabelcolors',
            *(
                f"{i}{j}"
                for i in ('status', 'beadstatus', 'orientation')
                for j in ('tag', 'color')
            ),
        })

        @ctrl.theme.observe(self._model.theme)
        def _onaxes(old, **_):
            if theme.intersection(old):
                getattr(self, '_threader').renew(ctrl, 'reset', True)

    def _addtodoc(self, ctrl, doc):
        "sets the plot up"
        self._addtodoc_data()
        self._addtodoc_fig()
        if not self._widgets:
            return [self._fig]

        itms      = [i.addtodoc(ctrl, doc)[0] for i in self._widgets]
        mode      = {'sizing_mode': ctrl.theme.get('main', 'sizingmode', 'fixed')}
        brds      = ctrl.theme.get("main", "borders", 5)
        width     = sum(i.width  for i in itms) + brds
        height    = max(i.height for i in itms) + brds

        return layouts.column(
            [
                layouts.row(
                    [
                        layouts.widgetbox(i, width = i.width, height = i.height)
                        for i in itms
                    ],
                    width  = width, height = height, **mode
                ),
                self._fig
            ],
            width  = max(width, self._fig.plot_width + brds),
            height = height + self._fig.plot_height,
            **mode,
        )

    def _addtodoc_data(self):
        self._stats  = ColumnDataSource(self._defaults)
        self._points = ColumnDataSource({i: [] for i in  [*_XCOLS, 'x', 'y']})

    def _addtodoc_fig(self):
        "build a figure"
        fig = figure(
            **self._model.theme.figargs,
            x_range = FactorRange(factors = self._defaults['x']),
            y_range = DataRange1d(bounds = (0, None), start = 0),
        )
        self._fig = fig

        for i in ('top', 'bottom'):
            self.attrs(self._model.theme.bars).addto(
                self._fig, source = self._stats, y = i,
            )
        self.attrs(self._model.theme.points).addto(
            self._fig, source = self._points
        )
        for i in ('vertices', 'box', 'median'):
            self.attrs(getattr(self._model.theme, i)).addto(
                self._fig, source = self._stats
            )

        self._topaxis = CategoricalAxis(
            x_range_name = "beadcount",
            axis_label   = self._model.theme.toplabel[0]
        )
        self._fig.extra_x_ranges = {'beadcount': FactorRange(factors = ['0'])}
        self._fig.add_layout(self._topaxis, 'above')

class _WhiskerBoxPlot(BasePlotter[FoVStatsPlot]):
    parent:    FoVStatsPlot

    _stats:    ColumnDataSource  = BasePlotter.attr()
    _points:   ColumnDataSource  = BasePlotter.attr()
    _defaults: Dict[str, list]   = BasePlotter.attr()
    _model:    FoVStatsPlotModel = BasePlotter.attr()
    _fig:      Figure            = BasePlotter.attr()
    _topaxis:  CategoricalAxis   = BasePlotter.attr()

    def _reset(self):
        "resets the data"
        self._compute()
        xaxis, yaxis, info = self._select()
        if info.shape[0] == 0:
            stats                         = self._defaults
            points: Dict[str, np.ndarray] = {'x': np.empty(0), 'y': np.empty(0)}
            idsort: np.ndarray            = np.arange(len(stats['x']))

        else:
            if yaxis == 'bead' or yaxis in xaxis:
                stats, points = self.__counts_select(info, xaxis, yaxis)
            else:
                stats, points = self.__stats_select(info, xaxis, yaxis)
            idsort = self.__argsort(xaxis, stats)
        self.__colors(xaxis, stats)

        tpe     = len(stats['beadcount']) and '/' in stats['beadcount'][0]
        factors = self.__bottomfactors((xaxis if info.shape[0] else []), stats, points)[idsort]
        yield (self._fig.x_range,  dict(factors = list(factors)))
        yield (
            self._fig.extra_x_ranges['beadcount'],
            dict(factors = self.__topfactors(factors, stats['beadcount'][idsort]))
        )
        yield (self._topaxis,      dict(axis_label = self._model.theme.toplabel[tpe]))
        yield (self._stats,        dict(data       = stats))
        yield (self._points,       dict(data       = points))
        yield (self._fig.yaxis[0], dict(axis_label = self._model.theme.yaxistag[yaxis]))
        yield (
            self._fig.xaxis[1],
            dict(axis_label = ' - '.join(self._model.theme.xaxistag[i] for i in xaxis))
        )

    _update = _reset

    def _isdefault(self) -> bool:
        return True

    def _computations(self, attr, tpe = pd.DataFrame, reqlen = True, **kwa):
        return super().computations(attr, self._model, tpe, reqlen, **kwa)

    def _compute_update(self, data, stretch):

        def _tag(name):
            return lambda x, y = getattr(self._model.theme, name+'tag'): y.get(x, x)

        return data.assign(
            **{
                i.key: data[i.key] * (stretch if i.factor == 'stretch' else i.factor)
                for i in COLS if i.factor and i.raw and i.key in data
            },
            **{
                i: data[i].apply(_tag(i))
                for i in data.columns
                if hasattr(self._model.theme, i+'tag')
            }
        )

    def _find_df(self, xaxis: List[str], yaxis: str) -> Tuple[List[str], str, pd.DataFrame]:
        dfpk:  pd.DataFrame = getattr(self, '_peak', pd.DataFrame())
        dfbd:  pd.DataFrame = getattr(self, '_bead', pd.DataFrame())
        optpk: List[str]    = []
        optbd: List[str]    = []
        if yaxis in dfpk:
            optpk = [i for i in xaxis if i in dfpk]
        if yaxis in dfbd:
            optbd = [i for i in xaxis if i in dfbd]

        if not optpk and not optbd:
            return xaxis, yaxis, pd.DataFrame()

        ycol = next(i for i in COLS if i.key == yaxis)
        if len(optbd) > len(optpk) or len(optbd) == len(optpk) and ycol.perbead:
            return optbd, yaxis, dfbd

        if not ycol.perbead or ycol.raw:
            return optpk, yaxis, dfpk

        return (
            optpk, yaxis,
            (
                dfpk
                .groupby(list({'track', 'bead', *optpk}))
                [yaxis]
                .sum()
                .reset_index()
            )
        )

    @abstractmethod
    def _select(self) -> Tuple[List[str], str, pd.DataFrame]:
        pass

    @abstractmethod
    def _compute(self):
        pass

    def __bottomfactors(self, xaxis, *dfs) -> np.ndarray:
        for stats in dfs:
            stats['x'] = tmp = np.array(list(stats['x']), dtype = np.str_)
            if len(tmp.shape) > 1:
                stats['x']    = np.zeros(len(tmp), dtype = np.object_)
                stats['x'][:] = [tuple(i) for i in tmp]

        ind = next((i for i, j in enumerate(xaxis) if j == 'track'), None)
        if ind is not None:
            if len(xaxis) == 1:
                tmp = set()
                for stats in dfs:
                    tmp.update(stats['x'])

                cnv = {np.str_(i): j for i, j in self._model.theme.tracknameconversion(tmp).items()}
                if cnv:
                    for stats in dfs:
                        stats['x'][:] = [cnv.get(i, i) for i in stats['x']]
            else:
                tmp = set()
                for stats in dfs:
                    tmp.update(i[ind] for i in stats['x'])

                cnv = {np.str_(i): j for i, j in self._model.theme.tracknameconversion(tmp).items()}
                if cnv:
                    for stats in dfs:
                        stats['x'][:] = [
                            (*i[:ind], cnv.get(i[ind], i[ind]), *i[ind+1:]) for i in stats['x']
                        ]
        return dfs[0]['x'] if len(dfs) else np.empty(0)

    @staticmethod
    def __topfactors(bottom, items) -> list:
        """
        Create same structue as for bottom categories & make sure there are no
        duplicate entries by adding an invisible character
        """
        if len(bottom) == 0:
            return []

        out:  List[str]      = []
        done: Dict[str, int] = {i: 0 for i in items}
        for i in items:
            out.append(i+"\u2063"*done[i])
            done[i] += 1

        if isinstance(bottom[0], str):
            return out
        return [(*j[:-1], i) for i, j in zip(out, bottom)]

    __NB = re.compile(r"^\d\+-.*")

    def __colors(self, xaxis, stats: pd.DataFrame):
        cnf    = self._model.theme
        dflt   = tohex(cnf.vertices.line_color)
        if not self._model.theme.uselabelcolors or len(stats['x']) == 0:
            stats['color'] = np.full(len(stats['x']), dflt)
            return

        tags   = getattr(cnf, xaxis[-1]+"tag", {})
        colors = tohex({tags[i]: j for i, j in getattr(cnf, xaxis[-1]+"color", {}).items()})
        stats['color'] = (
            np.full(len(stats['x']), dflt)  if not colors else
            np.array(
                [colors.get(i,     dflt) for i in stats['x']] if isinstance(stats['x'][0], str) else
                [colors.get(i[-1], dflt) for i in stats['x']]
            )
        )

    def __argsort(self, xaxis: List[str], stats):
        """
        Sort the x-axis either lexically or by order of importance as judged by
        stats['boxheight'].

        This is done by re-creating a dataframe containing all x-axis values,
        one columns by subcategory, then potentially inserting before some a
        column with the median of stats['boxheight'] per that category.
        Finally, the dataframe is sorted by values using all columns and the
        index is returned.
        """
        axes = pd.DataFrame(dict(
            {
                str(2*i+1): (
                    stats['x']
                    if len(xaxis) == 1 else
                    [stats['x'][k][i] for k in range(len(stats['x']))]
                )
                for i in range(len(xaxis))
            },
            value = -stats['boxcenter']
        ))

        for i in self._model.theme.getxaxisinfo('sortbyvalue', xaxis):
            axes.set_index(str(2*i+1), inplace = True)
            axes[str(2*i)] = axes.groupby(str(2*i+1)).value.median()
            axes.reset_index(inplace = True)

        def _cnt(itm):
            return itm.count(INVISIBLE)

        for i in range(1, 2*len(xaxis)+1, 2):
            col = axes[str(i)]
            if any(np.issubdtype(col.dtype, j) for j in (np.number, np.bool_)):
                if str(i-1) in axes:
                    # reverse orders: first the label, second the median value
                    axes.rename(columns = {str(i): str(i-1), str(i-1): str(i)}, inplace = True)
                continue

            vals = col.unique()
            if all(self.__NB.match(j) for j in vals):
                # the column is of type; ["1-track1", "2-track2", ...]
                # we keep only the track index
                axes[str(i)] = [int(j.split('-')) for j in col]

            elif any(j.startswith(INVISIBLE) for j in vals):
                # the column has labels sorted according to the invisible character.
                # count those and set them as the main order
                col = col.apply(_cnt)
                if str(i-1) in axes:
                    # reverse orders: first the label, second the median value
                    axes[str(i)]   = axes[str(i-1)]
                    axes[str(i-1)] = col
                else:
                    axes[str(i)]   = col

        axes.sort_values(
            [*(str(i) for i in range(2*len(xaxis)+1) if str(i) in axes), 'value'],
            inplace = True
        )
        return axes.index.values

    def __stats_select(
            self, info: pd.DataFrame, xaxis: List[str], yaxis: str
    ) -> _DATA:
        keys   = dict(level = list(range(len(xaxis))))
        data   = info.set_index(xaxis)[yaxis].rename('y').to_frame()
        stats  = data.groupby(**keys).y.agg(['median', boxbottom, boxtop])
        self.__beadscount(stats, info, xaxis, yaxis)

        spread = self._model.theme.spread*(stats.boxtop - stats.boxbottom)

        data   = (
            data
            .join((stats.boxbottom - spread).rename('bottomlimit'))
            .join((stats.boxtop    + spread).rename('toplimit'))
        )

        stats['boxcenter'] = (stats.pop('boxbottom') + stats.pop('boxtop'))*.5
        stats['boxheight'] = spread / self._model.theme.spread
        stats['bottom']    = data[data.y > data.bottomlimit].groupby(**keys).y.min()
        stats['top']       = data[data.y < data.toplimit].groupby(**keys).y.max()
        stats['x']         = list(stats.index)

        points = pd.concat([
            data[['y']][data.y <= data.bottomlimit],
            data[['y']][data.y >= data.toplimit],
        ]).join(stats['x'].to_frame())

        stats.reset_index(drop = True, inplace = True)
        points.reset_index(drop = True, inplace = True)

        threshold = self._model.theme.median.height
        stats.loc[stats['boxheight'] <= threshold, 'median']    = np.NaN
        stats.loc[stats['boxheight'] <= threshold, 'boxheight'] = threshold
        return (self._from_df(stats), self._from_df(points))

    def __counts_select(
            self, info: pd.DataFrame, xaxis: List[str], yaxis: str
    ) -> _DATA:
        if yaxis in xaxis:
            yaxis = 'bead'
        if yaxis in xaxis:
            yaxis = next(i for i in info.columns if i not in xaxis)
        keys   = dict(level = list(range(len(xaxis))))
        data   = info.set_index(xaxis)[yaxis].rename('boxheight').to_frame()
        stats  = (
            data.groupby(**keys).boxheight.count().to_frame()
            .assign(
                beadcount = lambda x: x.boxheight.apply(str),
                x         = lambda x: list(x.index),
                bottom    = np.NaN,
                top       = np.NaN,
                median    = np.NaN
            )
        )

        lvls                = (
            set(range(len(xaxis)))
            - set(self._model.theme.getxaxisinfo('norm', xaxis))
        )
        stats['boxheight'] *= (
            100
            / (
                stats['boxheight'].sum() if not lvls else
                data.groupby(level = sorted(lvls)).boxheight.count()
            )
        )
        stats['boxcenter'] = stats['boxheight'] * .5

        self.__beadscount(stats, info, xaxis, yaxis)
        stats.reset_index(drop = True, inplace = True)
        return (self._from_df(stats), {'x': [], 'y': []})

    @staticmethod
    def __beadscount(stats, info, xaxis, yaxis):
        if yaxis == 'bead' and len(info.bead.unique()) == len(info):
            stats['beadcount'] = info.groupby(xaxis)[yaxis].apply(lambda x: f'{len(x)}')
        elif 'bead' in xaxis:
            stats['beadcount'] = info.groupby(xaxis)[yaxis].apply(lambda x: f'1 / {len(x)}')
        else:
            stats['beadcount'] = (
                info.groupby(xaxis)['bead'].apply(lambda x: f'{len(set(x))} / {len(x)}')
            )

class _HairpinPlot(_WhiskerBoxPlot):
    _bead:      pd.DataFrame
    _peak:      pd.DataFrame
    _RENAMES:   ClassVar[Dict[str, str]] = {'hpin': 'hairpin'}
    _BEADOUT: ClassVar[FrozenSet[str]]   = frozenset({'closest', 'status'})

    def _select(self) -> Tuple[List[str], str, pd.DataFrame]:
        xaxis = self._model.theme.xaxis
        yaxis = self._model.theme.yaxis
        return self._find_df(xaxis, yaxis)

    def _compute(self):
        perpeakdf:   List[pd.DataFrame] = [self._peak] if hasattr(self, '_peak') else []
        perbeaddf:   List[pd.DataFrame] = [self._bead] if hasattr(self, '_bead') else []
        perpeakcols: List[str]          = list({
            i.key for i in COLS if i.label and not i.perbead and i.raw
        })
        perbeadcols: List[str]          = list({
            *(i.key for i in COLS if i.label and i.perbead and i.raw), *_IDS
        })

        hpin = self._model.display.hairpins
        ori  = self._model.display.orientations
        itr  = self._computations('_bead')
        for _, info in itr:
            info = self.selectbest(hpin, ori, info.reset_index()).rename(columns = self._RENAMES)
            info = itr.send(None if info.shape[0] == 0 else info)
            if info is not None:
                perbeaddf.append(info[perbeadcols])
                perpeakdf.append(
                    self._compute_update(
                        (
                            info.peaks.values[0][perpeakcols]
                            .assign(**{i: info[i].values[0] for i in perbeadcols})
                        ),
                        info.stretch.values[0]
                    )
                )

        for i, j in (('_peak', perpeakdf), ('_bead', perbeaddf)):
            if j:
                setattr(self, i, j[0] if len(j) == 1 else pd.concat(j, sort = False))
            elif hasattr(self, i):
                delattr(self, i)

        self.__compute_statusstats()

    def __compute_statusstats(self):
        if not hasattr(self, '_bead'):
            return

        self._peak = self._peak.assign(**dict.fromkeys(
            (
                *(f'f{i}perbd' for i in 'pn'),
                *(j+i for i in ('tp', 'fn') for j in ('', 'top', 'bottom'))
            ),
            0.0
        ))

        self._peak.set_index(['trackid', 'bead'], inplace = True)
        self._bead.set_index(['trackid', 'bead'], inplace = True)

        tags  = [
            self._model.theme.statustag[i] for i in ('truepos', 'falsepos', 'falseneg')
        ]

        def _set(dframe, col, values, norm):
            dframe.loc[values.index, col] = values / norm.loc[values.index]

        for strand, prefix in (('', ''), ('+', 'top'), ('-', 'bottom')):
            pks = self._peak
            if strand != '':
                pks = pks[pks.orientation == strand]

            if pks.shape[0] == 0:
                continue

            cnts  = (
                pks[np.isin(pks.status, tags)]
                .groupby(['status', 'trackid', 'bead'])
                .closest.apply(lambda x: len(x.unique()))
            )

            total = cnts.loc[[tags[0], tags[2]]].groupby(level = [1,2]).sum() / 100

            if tags[2] in cnts.index.levels[0]:
                if strand == '':
                    _set(self._peak, 'fnperbp', cnts.loc[tags[2]], self._bead.strandsize)
                _set(self._bead, f'{prefix}fn', cnts.loc[tags[2]], total)

            if strand == '' and tags[1] in cnts.index.levels[0]:
                _set(self._peak, 'fpperbp', cnts.loc[tags[1]], self._bead.strandsize)

            if tags[0] in cnts.index.levels[0]:
                _set(self._bead, f'{prefix}tp', cnts.loc[tags[0]], total)

        self._peak.reset_index(inplace = True)
        self._bead.reset_index(inplace = True)

class _PeaksPlot(_WhiskerBoxPlot):
    _bead: pd.DataFrame
    _peak: pd.DataFrame

    def _select(self) -> Tuple[List[str], str, pd.DataFrame]:
        xaxis = [
            i
            for i in self._model.theme.xaxis
            if not any(j.key == i and j.fit for j in COLS)
        ]
        if not xaxis:
            xaxis = ['track']
        yaxis = self._model.theme.yaxis
        if any(j.key == yaxis and j.fit for j in COLS):
            yaxis = 'hybridisationrate'
        return self._find_df(xaxis, yaxis)

    def _compute(self):
        cols: List[str] = list({
            i.key for i in COLS if i.raw and not i.fit and i.key != 'nblockages'
        })
        itr:  Generator = self._computations('_peak')
        lst:  List[pd.DataFrame] = [self._peak] if hasattr(self, '_peak') else []
        lst.extend(
            self._compute_update(itr.send(info.reset_index())[cols], self._model.theme.stretch)
            for _, info in itr
        )

        if lst:
            self._peak = (
                lst[0] if len(lst) == 1 else pd.concat(lst, sort = False)
            )
            tag:  str  = self._model.theme.statustag['']
            self._bead = (
                self._peak
                .groupby(_IDS).agg(
                    **{
                        i: (i, 'first')
                        for i in self._peak.columns
                        if any(j.key == i and j.perbead and j.key not in _IDS for j in COLS)
                    },
                    nblockages = ('status',  lambda x: (x == tag).sum())
                ).reset_index()
            )
        elif hasattr(self, '_peak'):
            del self._peak

class _BeadStatusPlot(_WhiskerBoxPlot):
    _bead:  pd.DataFrame
    _NAME:  ClassVar[str]       = 'beadstatus'
    _XAXIS: ClassVar[Set[str]]  = {'track', 'tracktag', 'beadstatus'}
    _YAXIS: ClassVar[str]       = 'bead'
    _COLS:  ClassVar[List[str]] = ['track', 'tracktag', 'trackid', 'bead']

    def _select(self) -> Tuple[List[str], str, pd.DataFrame]:
        xaxis = [i for i in self._model.theme.xaxis if i in self._XAXIS]
        return self._find_df(xaxis, self._YAXIS)

    def _compute(self):
        out: List[pd.DataFrame] = [self._bead] if hasattr(self, '_bead') else []

        itr = self._computations('_bead', (Exception, pd.DataFrame), False)
        for proc, info in itr:
            data = pd.DataFrame({
                'track': [trackname(proc.model[0])],
                self._NAME: (
                    info.errkey() if isinstance(info, ProcessorException) else
                    'bug'         if not isinstance(info, pd.DataFrame) else
                    'ok'          if info.shape[0] else
                    'empty'
                )
            })
            out.append(self._compute_update(itr.send(data), 1.))

        if out:
            self._bead = pd.concat(out) if len(out) > 1 else out[0]
