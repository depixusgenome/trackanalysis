#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Ramps widgets"
from    copy                    import deepcopy
from    typing                  import List, Tuple, Optional

import  numpy                   as     np
from    scipy.interpolate       import interp1d
from    bokeh                   import layouts
import  bokeh.core.properties   as     props
from    bokeh.models            import (
    Widget, DataTable, TableColumn, ColumnDataSource, Slider, BoxAnnotation,
    StringFormatter
)

from    qualitycontrol.view      import QCBeadStatusWidget, QCHairpinSizeWidget
from    taskcontrol.beadscontrol import TaskWidgetEnabler
from    utils                    import dataclass, dflt
from    utils.gui                import intlistsummary
from    view.plots               import CACHE_TYPE, DpxNumberFormatter
from    view.static              import route
from    ._model                  import RampPlotModel
from    ..processor              import RampStatsTask

@dataclass
class RampFilterConfig:
    "ramp filter config"
    name:   str = "ramps.filters"
    width:  int = 500
    height: int = 155

class DpxRamp(Widget):
    "Interface to filters needed for cleaning"
    __css__            = route("ramp.css")
    __javascript__     = route()
    __implementation__ = "_widget.ts"
    frozen             = props.Bool(True)
    minhfsigma         = props.Float(RampStatsTask.hfsigma[0])
    maxhfsigma         = props.Float(RampStatsTask.hfsigma[1])
    minextension       = props.Float(RampStatsTask.extension[0])
    fixedextension     = props.Float(RampStatsTask.extension[1])
    maxextension       = props.Float(RampStatsTask.extension[2])
    displaytype        = props.Int(0)

class RampFilterWidget:
    "All inputs for cleaning"
    __widget: DpxRamp
    RND = dict(minhfsigma     = 4, maxhfsigma   = 4,
               minextension   = 2, maxextension = 2,
               fixedextension = 2)
    def __init__(self, ctrl, model:RampPlotModel) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(RampFilterConfig())

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self.__widget = DpxRamp(
            name   = "Ramp:Filter",
            width  = self.__theme.width,
            height = self.__theme.height
        )

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
                task.extension = (new, *task.extension[1:])
            elif attr == "maxextension":
                task.extension = (*task.extension[:2], new)
            elif attr == "fixedextension":
                task.extension = (task.extension[0], new, task.extension[2])
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
    height: int         = 80
    columns: List[List] = dflt([["val",  "Consensus",     160, "0.00"],
                                ["err",  "Uncertainty",   160, "0.00"],
                                ["zmag", "Z magnet (mm)", 160, "0.00"]])
    units:  List[str]   = dflt(["(µm)", "(% strand size)"])
    rows:   List[float] = dflt([50, 66, 80, 95])
    @property
    def width(self) -> int:
        "the width of the widget"
        return sum(i[2] for i in self.columns) # pylint: disable=not-an-iterable

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
                                  width          = self.__theme.width,
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
    name:    str             = "ramp.zmageresults"
    step:    float           = .01
    value:   float           = -.4
    heights: Tuple[int, ...] = (48, 150)
    width:   int             = 500
    title:   str             = "Loosing {bead:.3f} ± {err:.3f} {unit} with Zmag ="
    ranges:  List[float]     = dflt([.05, .1, .2, .5, 1.])
    alpha                    = .5
    color                    = 'indianred'
    units:   List[str]       = dflt(RampZMagHintsTheme().units)
    columns: List[List]      = dflt([
        ["closing", "Closing ≥", 40, "0%"],
        ["count",   "Count",     40, "0"],
        ["percent", "(%)",       40, "0%"],
        ["beads",   "Beads",    180, ""]
    ])

class RampZMagResultsWidget:
    "Table containing discrete zmag values"
    __slider: Slider
    __src:    ColumnDataSource
    __box:    Optional[BoxAnnotation]
    def __init__(self, ctrl, model:RampPlotModel) -> None:
        self.__model = model
        self.__ctrl  = ctrl
        self.__theme = ctrl.theme.add(RampZMagResultsTheme())
        self.__box   = None

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        data = self.__data()
        self.__src     = ColumnDataSource(data.pop("table"))
        table          = DataTable(
            source         = self.__src,
            columns        = self.__columns(),
            editable       = False,
            index_position = None,
            width          = self.__theme.width,
            height         = self.__theme.heights[1]
        )
        self.__slider  = Slider(
            width  = self.__theme.width, height = self.__theme.heights[0], **data
        )

        @mainview.actionifactive(ctrl)
        def _onchange_cb(attr, old, new):
            ctrl.theme.update(self.__theme, value = new)
        self.__slider.on_change("value", _onchange_cb)
        return [self.__slider, table]

    def observe(self, mainview, ctrl):
        "observe the controller"
        @ctrl.theme.observe(self.__theme)
        def _observe(**_):
            if not mainview.isactive():
                return
            data = self.__data()
            self.__slider.update(title = data.pop('title'))
            self.__src.update(data = data.pop('table'))
            if self.__box is not None:
                zmag = self.__theme.value
                self.__box.update(left = zmag, right = zmag)

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        data = self.__data()
        resets[self.__src].update(data = data.pop('table'))
        resets[self.__slider].update(**data)
        if self.__box is not None:
            zmag = self.__theme.value
            resets[self.__box].update(left = zmag, right = zmag)

    def addline(self, fig):
        "add a vertical line at the current zmag"
        zmag = self.__theme.value
        self.__box = BoxAnnotation(
            left       = zmag,
            right      = zmag,
            fill_alpha = 0.,
            line_alpha = self.__theme.alpha,
            line_color = self.__theme.color
        )
        fig.add_layout(self.__box)

    def __columns(self):
        return [
            TableColumn(
                field     = i[0],
                title     = i[1],
                width     = i[2],
                formatter = DpxNumberFormatter(
                    format     = i[3],
                    text_align = 'right'
                ) if i[3] else StringFormatter()
            ) for i in self.__theme.columns
        ]

    def __data(self):
        data = self.__model.getdisplay("consensus")
        zmag = self.__theme.value
        return {
            **self.__update_slider(data, zmag),
            **self.__update_table(data, zmag),
        }

    def __update_slider(self, data, zmag):
        itms = dict(
            start = -.6,
            end   = -.3,
            step  = self.__theme.step,
            title = "",
            value = zmag,
        )

        if data is not None:
            name = "normalized" if self.__model.theme.dataformat == "norm" else "consensus"
            cols = [(name, i) for i in range(3)]+[("zmag", "")] # type: ignore
            arr  = data[cols]
            fcn  = lambda *x: interp1d(
                arr["zmag", ""],
                arr[x],
                assume_sorted = True,
                fill_value    = np.NaN,
                bounds_error  = False
            )(zmag)

            tit  = self.__theme.title
            unit = 1 if self.__model.theme.dataformat == "norm" else 0
            itms.update(
                start = np.nanmin(arr["zmag", ""]),
                end   = np.nanmax(arr["zmag", ""]),
                title = tit.format(
                    bead = fcn(name, 1),
                    zmag = zmag,
                    err  = (fcn(name, 2)-fcn(name,0))*.5,
                    unit = self.__theme.units[unit][1:-1]
                )
            )
        return itms

    def __update_table(self, data, zmag):
        table = {
            'closing':  [1.-i for i in self.__theme.ranges],
            **{i: [0]*len(self.__theme.ranges) for i in ('count', 'percent', 'beads')}
        }
        if data is not None:
            beads = np.array([
                *self.__model.display.status(self.__model.tasks.roottask, self.__ctrl)
                .get('ok', [])
            ])

            loss = (
                np.clip(
                    np.array([
                        interp1d(
                            data["zmag", ""],
                            data[i,  1],
                            assume_sorted = True,
                            fill_value    = 0.,
                            bounds_error  = False
                        )(zmag)
                        for i in beads
                    ]),
                    0.,
                    100.
                )
                / [data[i, 1].max() for i in beads]
            )

            notfound = loss >= -1
            splits   = []
            for i in self.__theme.ranges:
                good     = loss <= i
                splits.append(beads[good & notfound])
                notfound = ~good

            table.update(
                count   = [len(i)            for i in splits],
                percent = [len(i)/len(beads) for i in splits],
                beads   = [intlistsummary(i) for i in splits]
            )
        return {'table': table}

class RampHairpinSizeWidget(QCHairpinSizeWidget):
    "Table containing discrete zmag values"
    def _tabledata(self) -> np.ndarray:
        data = self._model.getdisplay("dataframe")
        if data is None:
            return np.empty(0)
        return data[data.status == "ok"].groupby("bead").extent.median().items()

class RampBeadStatusWidget(QCBeadStatusWidget):
    "Table containing beads per status"
    def __init__(self, ctrl, model):
        super().__init__(ctrl, model, status = {i: i for i in ("ok", "fixed", "bad")})
        self.__ctrl = ctrl

    def _data(self):
        return self._model.display.status(self._model.tasks.roottask, self.__ctrl)

class RampWidgets:
    "Everything dealing with changing the config"
    __objects : TaskWidgetEnabler
    def __init__(self, ctrl, model):
        self.__widgets = dict(filtering = RampFilterWidget(ctrl, model),
                              status    = RampBeadStatusWidget(ctrl, model),
                              zmag      = RampZMagResultsWidget(ctrl, model),
                              extension = RampHairpinSizeWidget(ctrl, model))

    def observe(self, mainview, ctrl):
        "observe the controller"
        for widget in self.__widgets.values():
            if hasattr(widget, 'observe'):
                widget.observe(mainview, ctrl)

    def create(self, view, ctrl, fig, width):
        "add to the gui"
        widgets = {i: j.addtodoc(view, ctrl) for i, j in self.__widgets.items()}
        self.__objects = TaskWidgetEnabler(widgets)
        self.__widgets['zmag'].addline(fig)
        names   = "filtering", "status", "zmag", "extension"
        lst     = sum((widgets[i] for i in names), [])
        for i in ('status', 'extension'):
            table = widgets[i][-1]
            table.columns[-1].width = width-sum(i.width for i in table.columns[:-1])
        for i in lst:
            i.width = width
            if i.height is None:
                i.height = 48
        return layouts.widgetbox(
            lst,
            height = sum(i.height for i in lst),
            width  = max(i.width for i in lst),
            **view.defaultsizingmode()
        )

    def reset(self, cache: CACHE_TYPE, disable: bool):
        "resets widgets"
        for ite in self.__widgets.values():
            getattr(ite, 'reset')(cache)
        self.__objects.disable(cache, disable)
