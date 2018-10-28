#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Ramps widgets"
from    copy                    import deepcopy
from    abc                     import ABC
from    typing                  import List, Dict, TypeVar

from    dataclasses             import dataclass, field
import  bokeh.core.properties   as     props
from    bokeh.models            import Widget, DataTable, TableColumn, ColumnDataSource

from    control.beadscontrol    import TaskWidgetEnabler
from    view.static             import ROUTE
from    view.plots              import CACHE_TYPE
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

    def addtodoc(self, _, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = DpxRamp(name = "Ramp:Filter")

        def _fcn_cb(attr, old, new):
            if new != old:
                name = "consensus" if attr == "normalize" else "dataframe"
                task = deepcopy(getattr(self.__model.config, name))
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
                elif attr == "displaytype":
                    if new == 0 or old == 0:
                        ctrl.theme.update(self.__model.theme, showraw = new == 0)
                    if new == 0:
                        return
                    task.normalize = new == 1
                else:
                    raise KeyError(f"unknown: {attr}")
                ctrl.theme.update(self.__model.config, **{name: task})
        for i in ('minhfsigma', 'maxhfsigma', 'minextension', 'fixedextension',
                  'maxextension', 'displaytype'):
            self.__widget.on_change(i, _fcn_cb)
        return [self.__widget]

    def reset(self, resets:CACHE_TYPE):
        "resets the widget when opening a new file, ..."
        info = {'minhfsigma'     : self.__model.config.dataframe.hfsigma[0],
                'maxhfsigma'     : self.__model.config.dataframe.hfsigma[1],
                'minextension'   : self.__model.config.dataframe.extension[0],
                'fixedextension' : self.__model.config.dataframe.extension[1],
                'maxextension'   : self.__model.config.dataframe.extension[2],
                'displaytype'    : (0 if self.__model.theme.showraw              else
                                    1 if self.__model.config.consensus.normalize else
                                    2)}
        (self.__widget if resets is None else resets[self.__widget]).update(**info)


@dataclass
class RampBeadStatusTheme:
    "RampBeadStatusTheme"
    name:   str             = "ramp.status"
    height: int             = 120
    status: Dict[str, str]  = dflt({i: i for i in ("ok", "fixed", "bad")})
    columns: List[List]     = dflt([["status", "status", 30],
                                    ["count",  "count",  30],
                                    ["beads",  "beads",  600]])

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

class WidgetMixin(ABC):
    "Everything dealing with changing the config"
    __objects = TaskWidgetEnabler
    def __init__(self, ctrl, model):
        self.__widgets = dict(filtering = RampFilterWidget(model),
                              status    = RampBeadStatusWidget(ctrl, model))

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
        self.__objects.disable(cache, disable)
