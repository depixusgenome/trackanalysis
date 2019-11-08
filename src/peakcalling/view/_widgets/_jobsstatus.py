#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the status of running jobs"
from dataclasses         import dataclass
from functools           import partial
from typing              import Dict, List, Set, Union
from bokeh.models        import Div, Select
from bokeh.document      import Document

from data.trackio        import TrackIOError
from taskmodel           import RootTask
from taskmodel.dataframe import DataFrameTask
from ...processor        import FitToHairpinTask
from .._model            import TasksModelController, BeadsScatterPlotStatus

def hairpinnames(self: TasksModelController) -> Set[str]:
    "return the hairpins currently used by the processors"
    items: Set[str] = set()
    for proc in getattr(self, 'processors', self).values():
        for task in proc.model[1:]:
            if isinstance(task, FitToHairpinTask):
                items.update(set(task.fit) - {None})
    return items

@dataclass
class JobsStatusBarConfig:
    "The config for the status bar"
    name:      str = 'peakcalling.view.statusbar'
    width:     int = 100
    height:    int = 28
    html:      str = '<table>{}</table>'
    sep:       str = ''
    fmt:       str = '<tr><td><b>{key}:</b></td><td>{i: 5d}</td><td>/ {j: 5d}</td></tr>'

class JobsStatusBar:
    "A status bar indicating the running jobs"
    _widget: Div
    _doc:    Document

    def __init__(self, **kwa):
        self._config: JobsStatusBarConfig       = JobsStatusBarConfig(**kwa)
        self._vals:   Dict[RootTask, List[int]] = {}
        self._idval:  int                       = -1

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        self._config = ctrl.theme.swapmodels(self._config)

    def addtodoc(self, _, doc) -> List[Div]:
        "create the widget"
        self._doc    = doc
        self._widget = Div(
            text   = self._text(),
            width  = self._config.width,
            height = self._config.height
        )

        return [self._widget]

    def observe(self, ctrl, model: TasksModelController):
        "observe the model"
        ctrl.display.observe(model.eventjobstart, partial(self._onstart, ctrl, model))
        ctrl.display.observe(model.eventname,     self._onevent)
        ctrl.display.observe(model.eventjobstop,  self._onstop)

    def _reset(self):
        if hasattr(self, '_doc'):
            txt = self._text()
            self._doc.add_next_tick_callback(lambda: self._widget.update(text = txt))

    def _text(self) -> str:
        itr = ((key, i, j) for key, (i, j) in self._vals.items() if key is not None)
        txt = self._config.fmt
        if '{key}' in txt:
            keys = {j: i for i, j in enumerate(self._vals.keys())}
            itms = (txt.format(key = keys[key], i = i, j = j) for key, i, j in itr)
        else:
            itms = (txt.format(i = i, j = j) for key, i, j in itr)
        return self._config.html.format(self._config.sep.join(itms)).replace(' ', '&nbsp;')

    def _onstop(self, idval, **_):
        if idval == self._idval:
            for i in self._vals.values():
                i[0] = i[1]
            self._reset()

    def _onstart(  # pylint: disable=too-many-arguments
            self, ctrl, model, idval, processors, calllater, **_
    ):
        if idval != model.jobs.display.calls:
            return

        @calllater.append
        def _later():
            self._idval = None
            self._vals.clear()

            def _keycnt(proc):
                try:
                    return sum(1 for _ in next(proc.run()).keys())
                except TrackIOError as exc:
                    ctrl.display.update("message", exc)

                    cache = proc.data.getcache(DataFrameTask)()
                    if cache:
                        return len(cache)
                return 0

            self._vals.update({j.model[0]: [0, _keycnt(j)] for j in processors})
            self._idval = idval

            self._reset()

    def _onevent(
            self,
            idval:     int,
            taskcache,
            beads:     List[int],
            **_
    ):
        if self._idval == idval:
            self._vals[taskcache.model[0]][0] += len(beads)
            self._reset()

@dataclass
class JobsHairpinSelectConfig:
    "configure hairpin choice"
    name:   str = 'peakcalling.view.hairpin'
    width:  int = 100
    height: int = 28
    allopt: str = 'all'

class JobsHairpinSelect:
    "A status bar indicating the running jobs"
    _widget: Select
    _doc:    Document

    def __init__(self):
        self._config = JobsHairpinSelectConfig()
        self._model  = BeadsScatterPlotStatus()

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        self._config = ctrl.theme.swapmodels(self._config)
        self._model  = ctrl.display.swapmodels(self._model)

    def addtodoc(self, ctrl, doc) -> List[Select]:
        "create the widget"
        self._doc    = doc
        self._widget = Select(
            options = [self._config.allopt],
            value   = self._config.allopt,
            width   = self._config.width,
            height  = self._config.height
        )

        @ctrl.action
        def _onvalue_cb(attr, old, new):
            ctrl.display.update(
                self._model,
                hairpins = (
                    set()   if new == self._config.allopt else
                    set(self._widget.options) - {new}
                )
            )

        self._widget.on_change("value", _onvalue_cb)
        return [self._widget]

    def observe(self, ctrl, mdl):
        "observe controller"

        def _reset():
            opts = self._options(mdl)
            self._doc.add_next_tick_callback(lambda: self._widget.update(**opts))

        @ctrl.display.observe(mdl.tasks.tasks.name)
        def _ontasks(action, change, **_):
            if 'task' not in action or getattr(change[1], 'sequences', None):
                _reset()

        @ctrl.display.observe(self._model)
        def _onmodel(old, **_):
            if 'hairpins' in old:
                _reset()

    def _options(self, model) -> Dict[str, Union[str, bool, List[str]]]:
        keys: Set[str]  = hairpinnames(model)
        opts: List[str] = [self._config.allopt, *sorted(keys)]
        return {
            'disabled': len(opts) < 2,
            'options':  opts,
            'value':   (
                self._config.allopt if len(opts) < 2 or not self._model.hairpins else
                next(iter(keys - self._model.hairpins), self._config.allopt)
            )
        }
