#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Ramps widgets"
from    copy                    import deepcopy
from    abc                     import ABC
from    typing                  import List, Dict, TypeVar, cast

import  numpy                   as     np
from    scipy.interpolate       import interp1d
from    dataclasses             import dataclass, field
import  bokeh.core.properties   as     props
from    bokeh.models            import Widget, DataTable, TableColumn, ColumnDataSource

from    control.beadscontrol    import TaskWidgetEnabler
from    view.static             import ROUTE
from    view.plots              import CACHE_TYPE, DpxNumberFormatter
from    ._model                 import RampPlotModel
from    ..processor             import RampDataFrameTask

Type = TypeVar("Type")
def dflt(default: Type, **kwa) -> Type:
    "return a field with default factory"
    return field(default_factory= lambda: deepcopy(default), **kwa)

class DpxRamp(Widget):
    "Interface to filters needed for cleaning"
    __css__            = ROUTE+"/ramp.css"
    __javascript__     = [ROUTE+"/jquery.min.js", ROUTE+"/jquery-ui.min.js"]
    __implementation__ = "_widget.coffee"
    frozen             = props.Bool(True)
    minhfsigma         = props.Float(RampDataFrameTask.hfsigma[0])
    maxhfsigma         = props.Float(RampDataFrameTask.hfsigma[1])
    minextension       = props.Float(RampDataFrameTask.extension[0])
    fixedextension     = props.Float(RampDataFrameTask.extension[1])
    maxextension       = props.Float(RampDataFrameTask.extension[2])
    displaytype        = props.Int(0)

class RampFilterWidget:
    "All inputs for cleaning"
    __widget: DpxRamp
    def __init__(self, model:RampPlotModel) -> None:
        self.__model = model

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = DpxRamp(name = "Ramp:Filter")

        @mainview.actionifactive(ctrl)
        def _fcn_cb(attr, old, new):
            if new == old:
                return

            if attr == "displaytype":
                dtype = ["raw", "norm", "cons"][new]
                if self.__model.theme.dataformat != dtype:
                    ctrl.theme.update(self.__model.theme, dataformat = dtype)
                return

            task = deepcopy(self.__model.config.dataframe)
            if attr == "minhfsigma":
                task.hfsigma = new, task.hfsigma[1]
            elif attr == "maxhfsigma":
                task.hfsigma = task.hfsigma[0], new
            elif attr == "minextension":
                task.extension = (new,) + task.extension[1:]
            elif attr == "maxextension":
                task.extension = task.extension[:2] + (new,)
            elif attr == "fixedextension":
                task.extension = task.extension[0], new, task.extension[2]
            else:
                raise KeyError(f"unknown: {attr}")
            if task != self.__model.config.dataframe:
                ctrl.theme.update(self.__model.config, dataframe = task)

        for i in ('minhfsigma', 'maxhfsigma', 'minextension', 'fixedextension',
                  'maxextension', 'displaytype'):
            self.__widget.on_change(i, _fcn_cb)
        return [self.__widget]

    def reset(self, resets:CACHE_TYPE):
        "resets the widget when opening a new file, ..."
        mdl  = self.__model
        info = {'minhfsigma'    : mdl.config.dataframe.hfsigma[0],
                'maxhfsigma'    : mdl.config.dataframe.hfsigma[1],
                'minextension'  : mdl.config.dataframe.extension[0],
                'fixedextension': mdl.config.dataframe.extension[1],
                'maxextension'  : mdl.config.dataframe.extension[2],
                'displaytype'   : ["raw", "norm", "cons"].index(mdl.theme.dataformat)}
        (self.__widget if resets is None else resets[self.__widget]).update(**info)

@dataclass
class RampBeadStatusTheme:
    "RampBeadStatusTheme"
    name:   str             = "ramp.status"
    height: int             = 160
    status: Dict[str, str]  = dflt({i: i for i in ("ok", "fixed", "bad")})
    columns: List[List]     = dflt([["status", "status", 40],
                                    ["count",  "count",  40],
                                    ["beads",  "beads",  400]])

class RampBeadStatusWidget:
    "Table containing beads per status"
    __widget: DataTable
    __src   : ColumnDataSource
    def __init__(self, ctrl, model:RampPlotModel) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(RampBeadStatusTheme())

    def addtodoc(self, *_) -> List[Widget]:
        "creates the widget"
        self.__src = ColumnDataSource(self.__data())
        cols       = [TableColumn(field = i[0], title = i[1], width = i[2])
                      for i in self.__theme.columns]
        self.__widget = DataTable(source         = self.__src,
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = sum(i[2] for i in self.__theme.columns),
                                  height         = self.__theme.height,
                                  name           = "Ramps:Status")
        return [self.__widget]

    def observe(self, ctrl):
        "observe the controller"
        def _on_df(**_):
            if "dataframe" in _:
                self.__src.update(data = self.__data())
        ctrl.display.observe(self.__model.display, _on_df)

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__src].update(data = self.__data())

    def __data(self):
        data    = self.__model.getdisplay("dataframe")
        status  = {"status": list(self.__theme.status.values()),
                   "count":  ["?", "?", "?"],
                   "beads":  ["?", "?", "?"]}
        if data is not None:
            data = data.groupby("bead").status.first().reset_index()
            data = data.groupby("status").bead.unique()
            for i, j in enumerate(self.__theme.status):
                beads              = data.loc[j] if j in data.index else []
                status["beads"][i] = ", ".join(str(i) for i in beads)
                status["count"][i] = len(beads)
        return status

@dataclass
class RampZMagHintsTheme:
    "RampBeadStatusTheme"
    name:   str         = "ramp.zmaghints"
    height: int         = 160
    columns: List[List] = dflt([["val",  "Consensus",     100, "0.00"],
                                ["err",  "Uncertainty",   100, "0.00"],
                                ["zmag", "Z magnet (mm)", 100, "0.00"]])
    units               = ("(µm)", "(% strand size)")
    rows                = [33, 50, 66, 80, 95]

class RampZMagHintsWidget:
    "Table containing discrete zmag values"
    __widget: DataTable
    __src   : ColumnDataSource
    def __init__(self, ctrl, model:RampPlotModel) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(RampZMagHintsTheme())

    def addtodoc(self, *_) -> List[Widget]:
        "creates the widget"
        self.__src = ColumnDataSource(self.__data())
        cols       = [TableColumn(field = i[0], title = i[1], width = i[2],
                                  formatter = DpxNumberFormatter(format     = i[3],
                                                                 text_align = 'right'))
                      for i in self.__theme.columns]
        self.__widget = DataTable(source         = self.__src,
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = sum(i[2] for i in self.__theme.columns),
                                  height         = self.__theme.height,
                                  name           = "Ramps:ZMagHints")
        return [self.__widget]

    def observe(self, ctrl):
        "observe the controller"

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__src].update(data = self.__data())
        unit = self.__theme.units[1 if self.__model.theme.dataformat == "norm" else 0]
        wcol = cast(list, self.__widgets.columns) # pylint: disable=no-member
        tcol = self.__theme.columns
        for col, tit in zip(wcol, tcol):
            resets[col].update(title = tit[1] + " " + unit)

        if self.__model.theme.dataformat == "norm":
            resets[wcol[0].formatter].update(format = "0")
        else:
            resets[wcol[0].formatter].update(format = tcol[0][-1])

    def __data(self):
        name = "normalized" if self.__model.theme.dataformat == "norm" else "consensus"
        data =  self.__model.getdisplay("consensus")
        vals = {i: [""]*len(self.__theme.rows) for i in ("zmag" ,"err")}
        vals["val"] = np.asarray(self.__theme.rows, dtype = "f4")
        if data is not None:
            cols = [(name, i) for i in range(3)]+[("zmag", "")] # type: ignore
            arr  = data[cols]

            if self.__model.theme.dataformat != "norm":
                vals["val"] *= np.nanmax(arr[name,1])/100.

            fcn          = lambda *x: interp1d(arr[name, 1], arr[x],
                                               assume_sorted = True,
                                               fill_value    = np.NaN,
                                               bounds_error  = False)(vals["val"])
            vals["zmag"] = fcn("zmag", "")
            vals["err"]  = fcn(name, 2) - fcn(name, 0)
        return vals

class WidgetMixin(ABC):
    "Everything dealing with changing the config"
    __objects = TaskWidgetEnabler
    def __init__(self, ctrl, model):
        self.__widgets = dict(filtering = RampFilterWidget(model),
                              status    = RampBeadStatusWidget(ctrl, model),
                              zmag      = RampZMagHintsWidget(ctrl, model))

    def _widgetobservers(self, ctrl):
        for widget in self.__widgets.values():
            if hasattr(widget, 'observe'):
                widget.observe(ctrl)

    def _createwidget(self, ctrl):
        widgets = {i: j.addtodoc(self, ctrl) for i, j in self.__widgets.items()}
        self.__objects = TaskWidgetEnabler(widgets)
        return widgets

    def _resetwidget(self, cache: CACHE_TYPE, disable: bool):
        for ite in self.__widgets.values():
            getattr(ite, 'reset')(cache)
        self.__objects.disable(cache, disable) # type: ignore
