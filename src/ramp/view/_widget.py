#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Ramps widgets"
from    copy                    import deepcopy
from    abc                     import ABC
from    typing                  import List, Dict, TypeVar

import  numpy                   as     np
from    scipy.interpolate       import interp1d
from    dataclasses             import dataclass, field
import  bokeh.core.properties   as     props
from    bokeh.models            import (Widget, DataTable, TableColumn,
                                        ColumnDataSource, Slider)

from    control.beadscontrol    import TaskWidgetEnabler
from    view.static             import ROUTE
from    view.plots              import CACHE_TYPE, DpxNumberFormatter
from    qualitycontrol.view     import QCBeadStatusWidget, QCHairpinSizeWidget
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
    RND = dict(minhfsigma     = 4, maxhfsigma   = 4,
               minextension   = 2, maxextension = 2,
               fixedextension = 2)
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
        for i, j in self.RND.items():
            info[i] = np.around(info[i], j)
        (self.__widget if resets is None else resets[self.__widget]).update(**info)

@dataclass
class RampZMagHintsTheme:
    "RampBeadStatusTheme"
    name:   str         = "ramp.zmaghints"
    height: int         = 125
    columns: List[List] = dflt([["val",  "Consensus",     160, "0.00"],
                                ["err",  "Uncertainty",   160, "0.00"],
                                ["zmag", "Z magnet (mm)", 160, "0.00"]])
    units:  List[str]   = dflt(["(µm)", "(% strand size)"])
    rows:   List[float] = dflt([50, 66, 80, 95])

class RampZMagHintsWidget:
    "Table containing discrete zmag values"
    __widget: DataTable
    __src   : ColumnDataSource
    def __init__(self, ctrl, model:RampPlotModel) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(RampZMagHintsTheme())

    def addtodoc(self, *_) -> List[Widget]:
        "creates the widget"
        self.__src    = ColumnDataSource(self.__data())
        self.__widget = DataTable(source         = self.__src,
                                  columns        = self.__columns(),
                                  editable       = False,
                                  index_position = None,
                                  width          = sum(i[2] for i in self.__theme.columns),
                                  height         = self.__theme.height,
                                  name           = "Ramps:ZMagHints")
        return [self.__widget]

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__src].update(data = self.__data())
        resets[self.__widget].update(columns = self.__columns())

    def __columns(self):
        unit        = 1 if self.__model.theme.dataformat == "norm" else 0
        cols        = [list(i) for i in self.__theme.columns]
        cols[0][1] +=  " " + self.__theme.units[unit]
        cols[1][1] +=  " " + self.__theme.units[unit]
        if self.__model.theme.dataformat == "norm":
            cols[0][-1] = "0"

        return [TableColumn(field = i[0], title = i[1], width = i[2],
                            formatter = DpxNumberFormatter(format     = i[3],
                                                           text_align = 'right'))
                for i in cols]

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
            vals["err"]  = (fcn(name, 2) - fcn(name, 0))*.5
        return vals

@dataclass
class RampZMagResultsTheme:
    "RampBeadStatusTheme"
    name:   str       = "ramp.zmageresults"
    step:   float     = .01
    value:  float     = -.4
    title:  str       = "Zmag test = {zmag:.2f}­→ looses {bead:.2f} ± {err:.2f} {unit}"
    units:  List[str] = dflt(RampZMagHintsTheme().units)

class RampZMagResultsWidget:
    "Table containing discrete zmag values"
    __widget: Slider
    def __init__(self, ctrl, model:RampPlotModel) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(RampZMagResultsTheme())

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = Slider(**self.__data(), show_value = False, tooltips = False)

        @mainview.actionifactive(ctrl)
        def _onchange_cb(attr, old, new):
            ctrl.theme.update(self.__theme, value = new)
        self.__widget.on_change("value", _onchange_cb)
        return [self.__widget]

    def observe(self, mainview, ctrl):
        "observe the controller"
        @ctrl.theme.observe(self.__theme)
        def _observe(**_):
            if mainview.isactive():
                self.__widget.update(title = self.__data()["title"])

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__widget].update(**self.__data())

    def __data(self):
        name = "normalized" if self.__model.theme.dataformat == "norm" else "consensus"
        data =  self.__model.getdisplay("consensus")
        zmag = self.__theme.value
        itms = dict(start = -.6, end = -.3, step = self.__theme.step, title = "",
                    value = zmag)
        if data is not None:
            cols = [(name, i) for i in range(3)]+[("zmag", "")] # type: ignore
            arr  = data[cols]
            fcn  = lambda *x: interp1d(arr["zmag", ""], arr[x],
                                       assume_sorted = True,
                                       fill_value    = np.NaN,
                                       bounds_error  = False)(zmag)

            tit  = self.__theme.title
            unit = 1 if self.__model.theme.dataformat == "norm" else 0
            itms.update(start = np.nanmin(arr["zmag", ""]),
                        end   = np.nanmax(arr["zmag", ""]),
                        title = tit.format(bead = fcn(name, 1),
                                           zmag = zmag,
                                           err  = (fcn(name, 2)-fcn(name,0))*.5,
                                           unit = self.__theme.units[unit][1:-1]))
        return itms

class RampHairpinSizeWidget(QCHairpinSizeWidget):
    "Table containing discrete zmag values"
    def _sliderdata(self) -> Dict[str, float]:
        task = self._model.config.dataframe.extension
        return {'start': task[0], "end": task[2]}

    def _tabledata(self) -> np.ndarray:
        data = self._model.getdisplay("dataframe")
        if data is None:
            return np.empty(0)
        return data[data.status == "ok"].groupby("bead").extent.median().items()

class RampBeadStatusWidget(QCBeadStatusWidget):
    "Table containing beads per status"
    def __init__(self, ctrl, model, **args):
        super().__init__(ctrl, model, **args)
        self.__ctrl = ctrl

    def _data(self):
        return self._model.display.status(self._model.tasks.roottask, self.__ctrl)

class WidgetMixin(ABC):
    "Everything dealing with changing the config"
    __objects : TaskWidgetEnabler
    def __init__(self, ctrl, model):
        self.__widgets = dict(filtering = RampFilterWidget(model),
                              status    = RampBeadStatusWidget(ctrl, model),
                              bead      = RampZMagHintsWidget(ctrl, model),
                              zmag      = RampZMagResultsWidget(ctrl, model),
                              extension = RampHairpinSizeWidget(ctrl, model))

    def _widgetobservers(self, ctrl):
        for widget in self.__widgets.values():
            if hasattr(widget, 'observe'):
                widget.observe(self, ctrl)

    def _createwidget(self, ctrl):
        widgets = {i: j.addtodoc(self, ctrl) for i, j in self.__widgets.items()}
        self.__objects = TaskWidgetEnabler(widgets)
        names   = "filtering", "status", "extension", "zmag", "bead"
        return sum((widgets[i] for i in names), [])

    def _resetwidget(self, cache: CACHE_TYPE, disable: bool):
        for ite in self.__widgets.values():
            getattr(ite, 'reset')(cache)
        self.__objects.disable(cache, disable)
