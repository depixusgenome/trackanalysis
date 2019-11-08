#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows FoV stats"
from   abc                     import abstractmethod
from   typing                  import (
    Dict, List, Tuple, Generator, ClassVar, Set, FrozenSet, Any
)
import re

import pandas as pd
import numpy  as np

from   bokeh                   import layouts
from   bokeh.models            import (
    ColumnDataSource, FactorRange, CategoricalAxis, Range1d
)
from   bokeh.plotting          import figure, Figure

import version
from   data.trackops           import trackname
from   view.colors             import tohex
from   view.threaded           import ThreadedDisplay
from   taskstore               import dumps
from   ._model                 import FoVStatsPlotModel, INVISIBLE, COLS, BeadsPlotTheme
from   ._widgets               import (
    JobsStatusBar, JobsHairpinSelect, PeakcallingPlotWidget, StorageExplorer
)
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


class XlsxReport:
    "export to xlsx"
    @classmethod
    def export(cls, plotter, path) -> bool:
        "export to xlsx"
        info = cls.dataframes(plotter)
        # pylint: disable=abstract-class-instantiated
        with pd.ExcelWriter(str(path), mode='w') as writer:
            for j, k in info:
                j.to_excel(writer, index = False, **k)

        return True

    @classmethod
    def dataframes(cls, plotter):
        "return the figure"
        mdl     = getattr(plotter, '_model')
        plotfcn = getattr(plotter, '_createplot')
        procs   = mdl.tasks.processors.values()

        info    = cls._export_plot(mdl, plotfcn(True), procs, {'bead': 'Bead status'})
        info.extend(cls._export_plot(mdl, plotfcn(False), procs, {}))
        info.extend(cls._export_git())
        info.extend(cls._export_tracks(procs))
        return info

    @staticmethod
    def _export_git() -> List[Tuple[pd.DataFrame, Dict[str, Any]]]:
        itms = [
            ("GIT Version:",      version.version()),
            ("GIT Hash:",         version.lasthash()),
            ("GIT Date:",         version.hashdate())
        ]
        return [(
            pd.DataFrame(dict(
                key   = [i for i, _ in itms],
                value = [j for _, j in itms],
            )),
            dict(header = False, sheet_name = "Tracks")
        )]

    @staticmethod
    def _export_tracks(processors) -> List[Tuple[pd.DataFrame, Dict[str, Any]]]:
        tracks = pd.DataFrame(dict(
            trackid = list(range(len(processors))),
            track   = [trackname(i.model[0]) for i in processors],
            tasks   = [
                dumps(j.model, ensure_ascii = False, indent = 4, sort_keys = True)
                for j in processors
            ]
        ))
        return [(
            tracks, dict(startrow = 5, sheet_name = "Tracks", freeze_panes = (5, len(tracks)))
        )]

    @staticmethod
    def _export_plot(
            mdl, plot, processors, sheetnames
    ) -> List[Tuple[pd.DataFrame, Dict[str, Any]]]:
        plot.compute()
        tracks = np.array([trackname(i.model[0]) for i in processors])
        cnv    = dict(mdl.theme.xaxistag, **mdl.theme.yaxistag)
        cnv.pop('bead')

        info: List[Tuple[pd.DataFrame, Dict[str, Any]]] = []
        for name in ('bead', 'peak'):
            sheet = getattr(plot, f'_{name}', None)
            if not isinstance(sheet, pd.DataFrame):
                continue

            info.append((
                sheet.assign(track = tracks[sheet.trackid.values]),
                dict(
                    header       = [cnv.get(k, k) for k in sheet.columns],
                    sheet_name   = sheetnames.get(name, f"{name.capitalize()} statistics"),
                    freeze_panes = (1, len(sheet))
                )
            ))
        return info

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
        self._plottheme = BeadsPlotTheme("peakcalling.view.beads.plot.theme")
        self._widgets   = (
            () if not widgets else
            (JobsStatusBar(), JobsHairpinSelect(), PeakcallingPlotWidget(), StorageExplorer())
        )
        self._defaults = dict(
            {i: np.array(['']) for i in  _XCOLS | self._DATAXCOLS},
            **{f'{j}': np.array([0.]) for j in self._DATAYCOLS},
        )
        self._defaults['color'] = ["green"]

    _reset = None   # added in _Threader.setup

    def gettheme(self):
        "get the model theme"
        return self._model.theme

    def createplot(self) -> BasePlotter:
        "runs the display"
        return self._createplot(getattr(_BeadStatusPlot, '_NAME') in self._model.theme.xaxis)

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        super().swapmodels(ctrl)
        self._plottheme = ctrl.theme.swapmodels(self._plottheme)
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

    def getfigure(self) -> Figure:
        "return the figure"
        return self._fig

    def export(self, path) -> bool:
        "return the figure"
        return XlsxReport.export(self, path)

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
            y_range = Range1d()
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

    def _createplot(self, beadstatus: bool) -> BasePlotter:
        "runs the display"
        procs = self._model.tasks.processors
        return (
            _BeadStatusPlot if beadstatus                   else
            _HairpinPlot    if BasePlotter.ishairpin(procs) else
            _PeaksPlot
        )(self, procs)

class _WhiskerBoxPlot(BasePlotter[FoVStatsPlot]):
    parent:    FoVStatsPlot

    _stats:     ColumnDataSource  = BasePlotter.attr()
    _points:    ColumnDataSource  = BasePlotter.attr()
    _defaults:  Dict[str, list]   = BasePlotter.attr()
    _model:     FoVStatsPlotModel = BasePlotter.attr()
    _fig:       Figure            = BasePlotter.attr()
    _topaxis:   CategoricalAxis   = BasePlotter.attr()
    _plottheme: BeadsPlotTheme    = BasePlotter.attr()

    def _reset(self):
        "resets the data"
        self.compute()
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

        yield (self._fig.y_range, self.__yrange(stats, points))
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
    def compute(self):
        "compute base dataframes"

    def __bottomfactors(self, xaxis, *dfs) -> np.ndarray:
        "fixes grouping of displayed statistics to 3"
        for stats in dfs:
            stats['x'] = tmp = np.array(list(stats['x']), dtype = np.str_)
            if len(tmp.shape) == 1:
                stats['x'] = tmp = np.hstack((tmp[:, None],) + (np.zeros_like(tmp)[:, None],) * 2)
            elif tmp.shape[1] < 3:
                stats['x'] = tmp = np.hstack((
                    tmp[:,0][:, None], np.zeros_like(tmp[:,0])[:,None], tmp[:,1][:, None]
                ))

            stats['x']    = np.zeros(len(tmp), dtype = np.object_)
            stats['x'][:] = [tuple(i) for i in tmp]

        ind = next((i for i, j in enumerate(xaxis) if j == 'track'), None)
        if ind is not None:
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

        arr = np.vstack([
            *(np.array([i[ind] for i in bottom]) for ind in range(len(bottom[0])-1)),
            np.array([j+'\u2063'*i for i, j in enumerate(items)])
        ]).T
        for ind in range(arr.shape[1]-1):
            vect = arr[:, ind]
            for i, j in enumerate(np.unique(vect)):
                vect[vect == j] = i*'\u2063'
        return [tuple(i) for i in arr]

    __NB = re.compile(r"^\d\+-.*")

    def __yrange(self, stats: pd.DataFrame, points: pd.DataFrame):
        vals = np.concatenate([
            points['y'], stats['bottom'], stats['boxcenter'] - stats['boxheight'] * .5,
            points['y'], stats['top'], stats['boxcenter'] + stats['boxheight'] * .5,
        ])

        return self._plottheme.newbounds(self._fig.y_range, vals, True)

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

    def compute(self):
        "compute base dataframes"
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
                        self.resetstatus(
                            self._model.theme.closest,
                            (
                                info.peaks.values[0][perpeakcols]
                                .assign(**{i: info[i].values[0] for i in perbeadcols})
                            )
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
            (f'f{i}perbp' for i in 'pn'), 0.0
        ))
        self._bead = self._bead.assign(**dict.fromkeys(
            (j+i for i in ('tp', 'fn') for j in ('', 'top', 'bottom')), 0.0
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

    def compute(self):
        "compute base dataframes"
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

    def compute(self):
        "compute base dataframes"
        out: List[pd.DataFrame] = [self._bead] if hasattr(self, '_bead') else []

        itr = self._computations('_bead', (Exception, pd.DataFrame), False)
        for proc, info in itr:
            data = pd.DataFrame({
                'track': [trackname(proc.model[0])],
                self._NAME: (
                    info.errkey() if isinstance(info, Exception) else
                    'bug'         if not isinstance(info, pd.DataFrame) else
                    'ok'          if info.shape[0] else
                    'empty'
                )
            })
            out.append(self._compute_update(itr.send(data), 1.))

        if out:
            self._bead = pd.concat(out) if len(out) > 1 else out[0]
