#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the status of running jobs"
from dataclasses    import dataclass
from functools      import partial
from typing         import Dict, List, Set, Union
from bokeh.models   import Div, Select
from bokeh.document import Document
from sequences      import read as _read
from taskmodel      import RootTask
from ._model        import TasksModelController, BeadsScatterPlotStatus

@dataclass
class JobsStatusBarConfig:
    "The config for the status bar"
    name:      str = 'peakcalling.view.statusbar'
    width:     int = 100
    height:    int = 28
    sep:       str = ' | '
    fmt:       str = '{i}/{j}'

class JobsStatusBar:
    "A status bar indicating the running jobs"
    _widget: Div
    _doc:    Document

    def __init__(self):
        self._config: JobsStatusBarConfig       = JobsStatusBarConfig()
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
        ctrl.display.observe(model.eventname,    partial(self._onevent, model))
        ctrl.display.observe(model.eventjobstop, self._onstop)

    def _reset(self):
        txt = self._text()
        self._doc.add_next_tick_callback(lambda: self._widget.update(text = txt))

    def _text(self) -> str:
        return self._config.sep.join(
            self._config.fmt.format(i = i, j = j)
            for key, (i, j) in self._vals.items()
            if key is not None
        )

    def _onstop(self, **_):
        for i in self._vals.values():
            i[0] = i[1]
        self._reset()

    def _onevent(
            self,
            model:     TasksModelController,
            idval:     int,
            taskcache,
            beads:     List[int],
            **_
    ):
        if self._idval != idval:
            self._idval = model.jobs.display.calls
            self._vals.clear()
            self._vals.update({
                i: [0, sum(1 for _ in next(j.run()).keys())]
                for i, j in model.processors.items()
            })

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
        items: Set[str] = set(_read(model.tasks.state.sequences))
        for _, procs in model.tasks.tasks.items():
            for task in procs.model:
                if getattr(task, 'sequences', None):
                    items |= {i for i, _ in _read(task.sequences)}
        opts = [self._config.allopt, *sorted(items)]
        return {
            'disabled': len(opts) < 2,
            'options':  opts,
            'value':   (
                self._config.allopt if len(opts) < 2 or not self._model.hairpins else
                next(iter(set(items) - self._model.hairpins), self._config.allopt)
            )
        }
