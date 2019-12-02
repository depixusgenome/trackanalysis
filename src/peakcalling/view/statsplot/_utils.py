#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"utils for statsplot"
from   typing import List, Tuple, Dict, Optional
import re
import numpy as np
import pandas as pd
from   ...model import INVISIBLE

def concat(lst):
    "concatenate dataframes"
    return lst[0] if len(lst) == 1 else pd.concat(lst, sort = False, ignore_index = True)

def binnedz(mdl, peak: pd.DataFrame, orig:str = 'peakposition', label: str = 'binnedz'):
    "compute binned z values"
    med  = np.round(peak[orig].median(), mdl.precision)
    arr  = peak[orig].values

    vals = np.round((arr-med)/mdl.step - .5) * mdl.step + med
    if mdl.width < mdl.step:
        vals[np.abs(vals - arr) > mdl.width] = np.NaN
    # convert to f8 as otherwise labels are too long
    peak[label] = np.round(vals.astype('f8'), mdl.precision)

def removereference(
        idref: int,
        xcols: List[str],
        ycol:  str,
        agg:   str,
        data:  pd.DataFrame
) -> pd.DataFrame:
    "subtrack the ref track values from other track values"

    keys  = [i for i in ('trackid', 'bead', 'status', 'closest') if i in data]
    if 'exclusive' in xcols and 'exclusive' in data:
        assert keys[-1] == 'closest'
        keys[-1] = 'exclusive'

    if len(keys) == 0 or keys[0] != 'trackid' or ycol in keys:
        return data

    if np.issubdtype(data[ycol].dtype, np.integer):
        data[ycol] = data[ycol].astype('f8')
    elif not np.issubdtype(data[ycol].dtype, np.float64):
        return data

    data.set_index(keys, inplace = True)
    if idref not in data.index.levels[0] or len(data.index.levels[0]) == 1:
        return data

    col   = data.groupby(level = list(range(len(keys)))).agg({ycol: agg})
    refdf = col.loc[idref, ycol]
    rids  = col.loc[idref].index
    for idtrack in data.index.levels[0]:
        if idtrack == idref:
            continue

        tids   = col.loc[idtrack].index
        common = tids & rids

        if len(common):
            col.loc[idtrack].loc[common, ycol] -= refdf.loc[common]

        diff = tids.difference(common)
        if len(diff):
            col.loc[idtrack].loc[diff, ycol] = np.NaN

    data.drop(columns = ycol, inplace = True)
    data = data.join(col)
    data.drop(index = idref, level = 0, inplace = True)
    data.reset_index(inplace = True)
    return data

def statscount(
        xaxis: List[str],
        xnorm: Optional[List[str]],
        yaxis: str,
        ynorm: Optional[Tuple[str, List[str]]],
        info:  pd.DataFrame
) -> pd.DataFrame:
    "compute the occurence percentage of `yaxis` as a function of `xaxis`"
    if yaxis in xaxis:
        yaxis = 'bead'
    if yaxis in xaxis:
        yaxis = next(i for i in info.columns if i not in xaxis)

    stats = (
        info
        .groupby(xaxis)[yaxis].count().rename('boxheight').to_frame()
        .assign(
            beadcount = lambda x: x.boxheight.apply(str),
            x         = lambda x: list(x.index),
            bottom    = np.NaN,
            top       = np.NaN,
            median    = np.NaN
        )
    )

    if isinstance(ynorm, tuple) and ynorm[0] in info:
        norm = (
            info[np.isin(info[ynorm[0]], list(ynorm[1]))]
            .set_index(xaxis)[yaxis].rename('boxheight').to_frame()
            .groupby(level = xaxis).boxheight.count()
        )
        stats['boxheight'] = 100 * norm / stats['boxheight']

    if xnorm is not None:
        lvls                = sorted(set(range(len(xaxis))) - set(xnorm))
        stats['boxheight'] *= (
            100 / (stats.groupby(level = lvls) if lvls else stats).boxheight.sum()
        )
    stats['boxcenter'] = stats['boxheight'] * .5
    return stats


def boxbottom(val):
    "the 1st quartile"
    return np.nanpercentile(val, 25)

def boxtop(val):
    "the 3rd quartile"
    return np.nanpercentile(val, 75)

def statsbox(
        spreadfactor: float,
        threshold:    float,
        xaxis:        List[str],
        yaxis:        str,
        info:         pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    "compute the boxplot distribution of `yaxis` as a function of `xaxis`"
    keys   = dict(level = list(range(len(xaxis))))
    data   = info.set_index(xaxis)[yaxis].rename('y').to_frame().dropna()
    stats  = data.groupby(**keys).y.agg(['median', boxbottom, boxtop])
    spread = spreadfactor*(stats.boxtop - stats.boxbottom)

    data   = (
        data
        .join((stats.boxbottom - spread).rename('bottomlimit'))
        .join((stats.boxtop    + spread).rename('toplimit'))
    )

    stats['boxcenter'] = (stats.pop('boxbottom') + stats.pop('boxtop'))*.5
    stats['boxheight'] = spread / spreadfactor
    stats['x']         = list(stats.index)

    for col in ('bottom', 'top'):
        comp       = np.greater if col == 'bottom' else np.less
        stats[col] = getattr(
            data[comp(data.y, getattr(data, f'{col}limit'))].groupby(**keys).y,
            ('min' if col == 'bottom' else 'max')
        )()

        limit = stats['boxcenter'] + stats['boxheight'] * (-.5 if col == "bottom" else .5)
        repl                 = np.isnan(stats[col])
        stats.loc[repl, col] = limit[repl]
        repl                 = comp(stats[col], limit)
        stats.loc[repl, col] = limit[repl]

    points = pd.concat(
        [
            data[['y']][data.y <= data.bottomlimit],
            data[['y']][data.y >= data.toplimit],
        ],
        sort         = False,
    ).join(stats['x'].to_frame())

    stats.loc[stats['boxheight'] <= threshold, 'median']    = np.NaN
    stats.loc[stats['boxheight'] <= threshold, 'boxheight'] = threshold
    return stats, points

def argsortxaxis(
        xaxis: List[str],
        xsort: List[bool],
        stats: Dict[str, np.ndarray],
        nbmatch = re.compile(r"^\d\+-.*")
):
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

    for isort in xsort:
        axes.set_index(str(2*isort+1), inplace = True)
        axes[str(2*isort)] = axes.groupby(str(2*isort+1)).value.median()
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
        if all(nbmatch.match(j) for j in vals):
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


_STATUS_IDS = ['baseline', '', 'truepos', 'singlestrand']
_IDS        = ['trackid', 'bead']
_NAVAL      = -9999
