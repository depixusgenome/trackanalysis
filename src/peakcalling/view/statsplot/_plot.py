#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows FoV stats"
from   abc                     import abstractmethod
from   typing                  import Dict, List, Tuple, ClassVar, FrozenSet

import pandas as pd
import numpy  as np

from   bokeh.models            import ColumnDataSource, CategoricalAxis, Range1d
from   bokeh.plotting          import Figure

from   view.colors             import tohex, palette
from   ...model                import FoVStatsPlotModel, COLS, BeadsPlotTheme
from   .._threader             import BasePlotter
from   ._utils                 import argsortxaxis, removereference, statscount, statsbox
from   ._view                  import FoVStatsPlot

_YCOLS  = frozenset({i.key for i in COLS if i.axis == 'y' and i.raw})

class StatsPlotWarning(RuntimeWarning):
    "used to warn the user"

class _WhiskerBoxPlot(BasePlotter[FoVStatsPlot]):
    parent:     FoVStatsPlot
    _frame:     Dict[str, list]
    _stats:     ColumnDataSource  = BasePlotter.attr()
    _points:    ColumnDataSource  = BasePlotter.attr()
    _defaults:  Dict[str, list]   = BasePlotter.attr()
    _model:     FoVStatsPlotModel = BasePlotter.attr()
    _fig:       Figure            = BasePlotter.attr()
    _topaxis:   CategoricalAxis   = BasePlotter.attr()
    _plottheme: BeadsPlotTheme    = BasePlotter.attr()
    _LINEAR:    ClassVar[FrozenSet[str]] = frozenset(['binnedz'])

    def getpointsframe(self) -> Dict[str, list]:
        "return data per bead & track"
        return getattr(self, '_frame', {})

    def getfigure(self) -> Figure:
        "return the figure"
        return self._fig

    def _iswrongaxis(self, xaxis = None) -> bool:
        if xaxis is None:
            xaxis = [i for i in self._model.theme.xaxis if i != 'xxx']

        islin = (
            self._model.theme.linear and len(xaxis) <= 2 and any(i in self._LINEAR for i in xaxis)
        )
        return islin is not isinstance(self._fig.x_range, Range1d)

    def _reset(self):
        "resets the data"
        self._frame = {}
        if self._iswrongaxis():
            yield (self._fig, dict(visible = False))
            return

        self.compute()
        xaxis, yaxis, info = self._select()
        if self._iswrongaxis(xaxis):
            yield (self._fig, dict(visible = False))
            return

        if info.shape[0] == 0:
            ref                           = False
            stats                         = self._defaults
            points: Dict[str, np.ndarray] = {'x': np.empty(0), 'y': np.empty(0)}
            idsort: np.ndarray            = np.arange(len(stats['x']))
            yield (StatsPlotWarning("No statistics available for this plot!"), "")
        else:
            stats, points, ref = self.__reset_select(info, xaxis, yaxis)
            idsort             = self.__reset_argsort(xaxis, stats)
            if len(stats['boxheight']) == 0 or np.all(np.isnan(stats['boxheight'])):
                yield (StatsPlotWarning("No statistics available for this plot!"), "")

        stats["xv"] = np.copy(stats["x"])
        stats["yv"] = stats['boxheight' if np.all(np.isnan(stats['median'])) else 'median']

        yield (self._fig, dict(visible = True))
        if isinstance(self._fig.x_range, Range1d):
            yield from self.__reset_continuous(xaxis, stats, points, idsort)
        else:
            yield from self.__reset_categorical(
                (xaxis if info.shape[0] else []), stats, points, idsort
            )

        tpe  = len(stats['beadcount']) and '/' in stats['beadcount'][0]
        yield (self._topaxis,      dict(axis_label = self._model.theme.toplabel[tpe]))
        yield (self._stats,        dict(data       = stats))

        self._frame = points
        if 'outlier' in points:
            good   = points['outlier']
            points = {i: np.asarray(j)[good] for i, j in points.items()}

        yield (self._points, dict(data = points))

        label = self._model.theme.yaxistag[yaxis]
        label = (
            label         if not ref else
            f'Δ({label})' if ' (' not in label else
            f'Δ({label[:label.rfind(" (")].strip()}) {label[label.rfind(" ("):]}'
        )
        yield (self._fig.yaxis[0], dict(axis_label = label))

        yield (self._fig.y_range, self.__reset_yrange(stats, points))
        yield (
            self._fig.xaxis[1],
            dict(axis_label = ' - '.join(self._model.theme.xaxistag[i] for i in xaxis))
        )

    _update = _reset

    def _isdefault(self) -> bool:
        return True

    def _computations(self, attr, tpe = pd.DataFrame, reqlen = True, **kwa):
        return super().computations(attr, self._model, tpe, reqlen, **kwa)

    def _compute_tags(self, data):
        def _tag(name):
            return lambda x, y = getattr(self._model.theme, name+'tag'): y.get(x, x)

        return data.assign(
            **{
                i: data[i].apply(_tag(i))
                for i in data.columns
                if hasattr(self._model.theme, i+'tag')
            }
        )

    @staticmethod
    def _compute_update(data, stretch):
        return data.assign(
            **{
                i.key: data[i.key] * (stretch if i.factor == 'stretch' else i.factor)
                for i in COLS if i.factor and i.raw and i.key in data
            },
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
                .agg({yaxis: 'sum', 'trackid': 'first'})
                .reset_index()
            )
        )

    @abstractmethod
    def _select(self) -> Tuple[List[str], str, pd.DataFrame]:
        pass

    @abstractmethod
    def compute(self):
        "compute base dataframes"

    def __reset_yrange(self, stats: pd.DataFrame, points: pd.DataFrame):
        vals = np.concatenate([
            points['y'], stats['bottom'], stats['boxcenter'] - stats['boxheight'] * .5,
            points['y'], stats['top'], stats['boxcenter'] + stats['boxheight'] * .5,
        ])

        return self._plottheme.newbounds(self._fig.y_range, vals, True)

    def __reset_colors(self, ind:int, xaxis: List[str], stats: pd.DataFrame):
        cnf    = self._model.theme
        dflt   = tohex(cnf.vertices.line_color)
        if not self._model.theme.uselabelcolors or len(stats['x']) == 0:
            stats['color'] = np.full(len(stats['x']), dflt)
            return

        tags = getattr(cnf, xaxis[ind]+"tag", {}) if len(xaxis) else {}
        if tags:
            colors = tohex({
                tags[i]: j for i, j in getattr(cnf, xaxis[ind]+"color", {}).items()
            })
        elif (
                self._model.theme.defaultcolors != 'none'
                and isinstance(stats['x'][0], (list, tuple))
                and len(stats['x'][0]) > 1
        ):
            vals   = [i[ind] for i in stats['x']]
            vals   = sorted(j for i, j in enumerate(vals) if j not in vals[:i])
            colors = palette(self._model.theme.defaultcolors, vals)
        else:
            stats['color'] = np.full(len(stats['x']), dflt)
            return

        if colors and isinstance(stats['x'][0], tuple) and len(stats['x'][0]) > ind:
            stats['color'] = np.array([colors.get(i[ind], dflt) for i in stats['x']])
        elif colors and isinstance(stats['x'][0], str):
            stats['color'] = np.array([colors.get(i,      dflt) for i in stats['x']])
        else:
            stats['color'] = np.full(len(stats['x']), dflt)

    def __reset_argsort(self, xaxis: List[str], stats):
        """
        Sort the x-axis either lexically or by order of importance as judged by
        stats['boxheight'].

        This is done by re-creating a dataframe containing all x-axis values,
        one columns by subcategory, then potentially inserting before some a
        column with the median of stats['boxheight'] per that category.
        Finally, the dataframe is sorted by values using all columns and the
        index is returned.
        """
        return argsortxaxis(
            xaxis,
            self._model.theme.getxaxisinfo('sortbyvalue', xaxis),
            stats
        )

    def __reset_select(
            self, info: pd.DataFrame, xaxis: List[str], yaxis: str
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray], bool]:
        ref = False
        if yaxis == 'bead' or yaxis in xaxis:
            ynorm  = self._model.theme.yaxisnorm
            xnorm  = (
                None if ynorm and ynorm[0] in info  and 'hairpin' in info else
                self._model.theme.getxaxisinfo('norm', xaxis)
            )
            if xnorm is None:
                tags  = self._model.theme.statustag.get
                ynorm = ynorm[0], tuple(tags(i, i) for i in ynorm[1])
            else:
                ynorm = None
            stats  = statscount(xaxis, xnorm, yaxis, ynorm, info)
            points = pd.DataFrame(columns = ('x', 'y', 'bead', 'track'))
        else:
            if self._model.display.reference in self._procs:
                info = removereference(
                    id(self._model.display.reference), xaxis, yaxis,
                    self._model.theme.refagg,
                    info
                )
                ref = True

            stats, points = statsbox(
                self._model.theme.spread,
                self._model.theme.median.height,
                xaxis, yaxis, info
            )

        stats['beadcount'] = (
            info.groupby(xaxis)
            [yaxis if 'bead' in xaxis else 'bead']
            .apply(
                (lambda x: f'{len(x)}')
                if yaxis == 'bead' and len(info.bead.unique()) == len(info) else
                (lambda x: f'1 / {len(x)}')
                if 'bead' in xaxis else
                (lambda x: f'{len(set(x))} / {len(x)}')
            )
        )
        stats.reset_index(inplace = True)

        return self._from_df(stats), self._from_df(points), ref

    def __reset_continuous(self, xaxis, stats, points, idsort):
        if len(xaxis) == 2:
            ind = 1 if xaxis[1] in self._LINEAR else 0
            self.__reset_colors(0 if ind else 1, xaxis, stats)
        else:
            self.__reset_colors(0, xaxis, stats)
            ind = 1e6

        def _float(val):
            try:
                return float(val)
            except ValueError:
                return np.NaN

        for dframe in (stats, points):
            if len(dframe['x']) and np.isscalar(dframe['x'][0]):
                dframe['x'] = np.array([_float(i) for i in dframe['x']])

            elif len(dframe['x']) and len(dframe['x'][0]) > ind:
                dframe['x'] = np.array([_float(i[ind]) for i in dframe['x']])

            else:
                dframe['x'] = np.full(len(dframe['x']), np.NaN, dtype = 'f4')

        factors = list(stats['x'])
        yield (
            self._fig.x_range,
            self._plottheme.newbounds(
                self._fig.x_range,
                np.concatenate([
                    stats['x'] - self._model.theme.median.width*.5,
                    stats['x'] + self._model.theme.median.width*.5
                ]),
                True
            )
        )

        if not factors or np.all(np.isnan(factors)):
            yield (
                self._topaxis,
                dict(ticker = [0], major_label_overrides = {}, visible = False)
            )
        else:
            yield (
                self._topaxis,
                dict(
                    visible               = True,
                    ticker                = factors,
                    major_label_overrides = dict(zip(factors, stats['beadcount'][idsort]))
                )
            )

        width = (
            self._model.theme.binnedz.width if xaxis[0] == 'binnedz' else
            self._model.theme.binnedbp.width
        )
        for rend in self._fig.renderers:
            if hasattr(rend.glyph, 'width') and rend.glyph.name:
                mdl = getattr(self._model.theme, rend.glyph.name)
                yield (rend.glyph, dict(width = mdl.width*width))

    def __reset_categorical(self, xaxis, stats, points, idsort):
        self.__reset_colors(len(xaxis)-1, xaxis, stats)  # no raw "-1" as arg for this method
        factors = self.__reset_categorical_bottomfactors(xaxis, stats, points)[idsort]
        yield (self._fig.x_range,  dict(factors = list(factors)))
        yield (
            self._fig.extra_x_ranges['beadcount'],
            dict(factors = self.__reset_categorical_topfactors(factors, stats['beadcount'][idsort]))
        )

    def __reset_categorical_bottomfactors(self, xaxis, *dfs) -> np.ndarray:
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
                if len(stats['x']) and len(stats['x'][0]) > ind:
                    tmp.update(i[ind] for i in stats['x'])

            cnv = {np.str_(i): j for i, j in self._model.theme.tracknameconversion(tmp).items()}
            if cnv:
                for stats in dfs:
                    stats['x'][:] = [
                        (*i[:ind], cnv.get(i[ind], i[ind]), *i[ind+1:]) for i in stats['x']
                    ]
        return dfs[0]['x'] if len(dfs) else np.empty(0)

    @staticmethod
    def __reset_categorical_topfactors(bottom, items) -> list:
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
