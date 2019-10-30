#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the status of running jobs"
from copy                import deepcopy
from contextlib          import contextmanager
from dataclasses         import dataclass
from functools           import partial
from itertools           import chain
from typing              import Dict, List, Set, Union, Any
from bokeh.models        import Div, Select, Button
from bokeh.document      import Document

from data.trackops       import trackname
from modaldialog         import dialog
from modaldialog.builder import tohtml
from taskmodel           import RootTask
from view.fonticon       import FontIcon
from utils.logconfig     import getLogger
from ..processor         import FitToHairpinTask
from ._model             import (
    TasksModelController, BeadsScatterPlotStatus, AxisConfig, FoVStatsPlotModel,
    COLS, INVISIBLE
)

LOGS = getLogger(__name__)

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
        ctrl.display.observe(model.eventjobstart, partial(self._onstart, model))
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

    def _onstart(self, model, idval, **_):
        if idval == model.jobs.display.calls:
            self._idval = None
            self._vals.clear()
            self._vals.update({
                i: [0, sum(1 for _ in next(j.run()).keys())]
                for i, j in model.processors.items()
            })
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

@dataclass
class PeakcallingPlotConfig:
    "configure axes choice"
    name:   str = 'peakcalling.view.axes'
    width:  int = 100
    height: int = 28
    label:  str = ''
    icon:   str = 'cog'
    none:   str = "none"

class PeakcallingPlotModel:     # pylint: disable=too-many-instance-attributes
    "configure xaxis choice"
    def __init__(self, mdl: FoVStatsPlotModel, cnf: PeakcallingPlotConfig):
        self.closest:        int     = mdl.theme.closest
        self.stretch:        float   = round(mdl.theme.stretch, 2)
        self.uselabelcolors: bool    = mdl.theme.uselabelcolors
        self.tracknames:     str     = mdl.theme.tracknames
        self.xinfo: List[AxisConfig] = [
            AxisConfig('xxx') if i >= len(mdl.theme.xinfo) else deepcopy(mdl.theme.xinfo[i])
            for i in range(3)
        ]
        self.yaxis:      str             = mdl.theme.yaxis

        procs                            = mdl.tasks.processors
        self.roots:      List[RootTask]  = list(procs)
        self.beadmask:   List[List[int]] = [list(mdl.display.beads.get(i, ())) for i in procs]
        self.tracktag:   List[str]       = [mdl.display.tracktag.get(i, cnf.none) for i in procs]
        self.tracksel:   List[bool]      = [i not in mdl.display.roots for i in procs]
        self.statustag:  List[str]       = list(mdl.theme.statustag.values())
        self.beadstatustag:    List[str]       = list(mdl.theme.beadstatustag.values())
        self.hairpins:   List[str]       = sorted(hairpinnames(procs))
        self.hairpinsel: List[bool]      = [i not in mdl.display.hairpins for i in self.hairpins]
        self.orientationsel: List[bool]  = [
            i not in mdl.display.orientations
            for i in mdl.theme.orientationtag.keys()
        ]
        self.norm: str = next(
            (str(i) for i in self.xinfo if not i.norm and i.key != 'xxx'), '0'
        )

    reset = __init__

    def diff(
            self, right: 'PeakcallingPlotModel', model: FoVStatsPlotModel
    ) -> Dict[str, Dict[str, Any]]:
        "return a dictionnary of changed items"
        diff: Dict[str, Dict[str, Any]] = {'display': {}, 'theme': {}}
        for i, j, k in chain(
                self.__diff_axes(right),
                self.__diff_tracks(right),
                self.__diff_hairpins(right),
                self.__diff_orientation(right, model),
                self.__diff_tags("statustag", right, model),
                self.__diff_tags("beadstatustag",   right, model),
                self.__diff_attr(right)
        ):
            diff[i][j] = k
        return diff

    def __diff_attr(self, right):
        for i in ('closest', 'stretch', 'uselabelcolors'):
            if abs(getattr(self, i) - getattr(right, i)) > 1e-2:
                yield ('theme', i, getattr(right, i))
        for i in ('tracknames',):
            if getattr(self, i) != getattr(right, i):
                yield ('theme', i, getattr(right, i))

    def __diff_axes(self, right: 'PeakcallingPlotModel'):
        cpy = deepcopy(right.xinfo)
        for i, j in enumerate(cpy):
            j.norm = right.norm == '0' or right.norm != str(i+1)

        if any(i.__dict__ != j.__dict__ for i, j in zip(self.xinfo, right.xinfo)):
            out = (
                'theme', 'xinfo',
                [
                    j for i, j  in enumerate(right.xinfo)
                    if j.name != 'xxx' and j.name not in {k.name for k in right.xinfo[:i]}
                ]
            )
            yield out
        if self.yaxis != right.yaxis:
            yield ('theme', 'yaxis', right.yaxis)

    def __diff_tags(self, attr: str, right: 'PeakcallingPlotModel', model: FoVStatsPlotModel):
        leftv:  List[str]      = getattr(self,  attr)
        rightv: List[str]      = getattr(right, attr)
        mdl:    Dict[str, str] = getattr(model.theme, attr)

        if leftv != rightv:
            # reset some values
            factory: Dict[str, str] = getattr(type(model.theme)(), attr)
            for idx, j in enumerate(mdl):
                if (
                        not rightv[idx]
                        or rightv[idx].replace(INVISIBLE, '') == factory[j].replace(INVISIBLE, '')
                ):
                    rightv[idx] = factory[j]

        if leftv != rightv:
            # add invisible characters such that the prior order be preserved
            dflt: Dict[str, int] = {i: 0 for i in rightv}
            for i, j in zip(rightv, leftv):
                dflt[i] = max(dflt[i], j.count(INVISIBLE))
            yield (
                'theme', attr,
                {i: INVISIBLE * dflt[j] + j.replace(INVISIBLE, '') for i, j in zip(mdl, rightv)}
            )

    def __diff_orientation(self, right: 'PeakcallingPlotModel', model: FoVStatsPlotModel):
        if self.orientationsel != right.orientationsel:
            yield (
                'display', 'orientations',
                {
                    j for i, j in
                    zip(right.orientationsel, model.theme.orientationtag)
                    if not i
                }
            )

    def __diff_hairpins(self, right: 'PeakcallingPlotModel'):
        if self.hairpinsel != right.hairpinsel:
            yield (
                'display', 'hairpins',
                {j for i, j in zip(right.hairpinsel, right.hairpins) if not i}
            )

    def __diff_tracks(self, right: 'PeakcallingPlotModel'):
        if self.tracksel != right.tracksel:
            yield (
                'display', 'roots',
                {j for i, j in zip(right.tracksel, right.roots) if not i}
            )

        if any(i != j for i, j in zip(self.beadmask, right.beadmask)):
            yield (
                'display', 'beads',
                {
                    i: k
                    for i, j, k in zip(right.roots, self.beadmask, right.beadmask)
                    if j != k
                }
            )

        if any(i != j for i, j in zip(self.tracktag, right.tracktag)):
            yield ('display', 'tracktag', dict(zip(right.roots, right.tracktag)))

class _JSWidgetVericicator:
    "returns the js code to deal with the modal dialog"
    def __init__(self, xaxis:str, yaxis:str):
        self.beadstatus = next(i for i, j in self.__cols(xaxis) if j.key == 'beadstatus')
        self.yaxisbeads = [
            i
            for i, j in self.__cols(yaxis, ('fnperbp', 'fpperbp', 'bead'))
            if j.axis == 'y' and j.perbead
        ]
        self.xaxispeaks = [i for i, j in self.__cols(xaxis) if j.axis == 'x' and not j.perbead]

    @staticmethod
    def __cols(txt, reject = ()):
        for i, j in enumerate(txt.split('|')[1:-1]):
            j   = j[:j.find(':')]
            if j not in reject:
                col = next((k for k in COLS if k.key == j), None)
                if col:
                    yield (i, col)

    def __call__(self):
        axes = [
            *(f'document.getElementsByName("xinfo[{i}].name")[0]' for i in range(3)),
            'document.getElementsByName("yaxis")[0]'
        ]
        return f"""
            <script>
            function _reset_xinfo()    {{ {self.__reset(axes)} }};
            function _on_xinfo_name(_) {{ _reset_xinfo(); _reset_xinfo(); }};

            try {{ [{','.join(axes)}].forEach(itm => itm.onchange = _on_xinfo_name); }}
            catch(error) {{}}

            _on_xinfo_name(0);
            </script>
        """

    def __reset(self, axes):
        return f"""
            var i     = 0;
            var elems = [{','.join(axes[:-1])}];
            var yaxis = {axes[-1]};
            var ixid  = {self.xaxispeaks};
            var iyid  = {self.yaxisbeads};

            [{','.join(axes)}].forEach(function(itm){{
                var i = 0;
                for(i = 0; i < itm.options.length; ++i)
                    itm.options[i].disabled = false;
            }});

            {self.__reset_beadstatus()}
            {self.__reset_peaskvsbeads()}
            {self.__reset_xxx()}
            {self.__reset_norm()}
        """

    def __reset_beadstatus(self) -> str:
        return """
            var ibeadstat = [
                elems[0].selectedIndex, elems[1].selectedIndex-1, elems[2].selectedIndex-1
            ];
            if(ibeadstat.includes(%(beadstatus)s)){
                yaxis.selectedIndex = 0;
                for(i = 1; i < yaxis.options.length; i++)
                    yaxis.options[i].disabled = true;

                if(ibeadstat[0] == %(beadstatus)s)
                    ixid.forEach(function(ind){
                        elems.slice(1).forEach(itm => itm.options[ind+1].disabled = true);
                    });
                if(ibeadstat[1] == %(beadstatus)s)
                    ixid.forEach(ind => elems[2].options[ind+1].disabled = true);
            }
        """ % dict(beadstatus = self.beadstatus)

    def __reset_peaskvsbeads(self) -> str:
        return """
            else if(
                ixid.includes(elems[0].selectedIndex)
                || ixid.includes(elems[1].selectedIndex-1)
                || ixid.includes(elems[2].selectedIndex-1)
            )
            {
                iyid.forEach(ind => yaxis.options[ind].disabled = true);
                elems.slice(1).forEach(itm => itm.options[%(beadstatus)s+1].disabled = true);
            }
        """ % dict(beadstatus = self.beadstatus)

    @staticmethod
    def __reset_xxx() -> str:
        return """
            elems.slice(1).forEach(itm => itm.options[elems[0].selectedIndex+1].disabled = true);
            elems[2].options[elems[1].selectedIndex].disabled = true;

            elems.forEach(function(itm){
                if(itm.options[itm.selectedIndex].disabled)
                    itm.selectedIndex = 0
            });

            elems[2].disabled = elems[1].selectedIndex == 0;
            if(elems[2].disabled)
            { elems[2].selectedIndex = 0; }
            elems[2].parentElement.parentElement.style.display = elems[2].disabled ? "none" : null;
        """

    @staticmethod
    def __reset_norm() -> str:
        return """
            var el4 = document.getElementsByName("norm")[0];
            el4.disabled = yaxis.selectedIndex != 0;
            for(i = 1; i < el4.options.length; i++)
            {
                var itm       = el4.options[i];
                itm.innerHTML = elems[i-1].options[elems[i-1].selectedIndex].innerHTML;
                itm.disabled  = elems[i-1].selectedIndex == 0
            }
            if(el4.disabled || el4.options[el4.selectedIndex].disabled)
                el4.selectedIndex = 0;

            el4.parentElement.parentElement.style.display = yaxis.selectedIndex == 0 ? null: "none";
        """

class PeakcallingPlotWidget:
    "Configure the plot"
    _widget:  Button
    _doc:     Document

    def __init__(self):
        self._model   = FoVStatsPlotModel()
        self._theme   = PeakcallingPlotConfig()

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        self._theme = ctrl.theme.swapmodels(self._theme)
        self._model.swapmodels(ctrl)

    def addtodoc(self, ctrl, doc) -> List[Button]:
        "creates the widget"
        self._widget = Button(
            width  = self._theme.width,
            height = self._theme.height,
            label  = self._theme.label,
            icon   = (
                None if self._theme.icon is None else FontIcon(iconname = self._theme.icon)
            )
        )

        @self._widget.on_click
        def _onclick_cb():
            "method to trigger the modal dialog"
            try:
                current = PeakcallingPlotModel(self._model, self._theme)
                return dialog(
                    doc,
                    **tohtml(self._body(current), current, current),
                    context = partial(self._onsubmit, ctrl, deepcopy(current), current),
                    model   = current,
                    always  = True
                )
            except Exception as exc:  # pylint: disable=broad-except
                LOGS.exception(exc)
                tohtml(f"ERROR: {exc}")

        return [self._widget]

    @contextmanager
    def _onsubmit(self, ctrl, current, changed, _):
        yield

        diff = current.diff(changed, self._model)
        if not diff:
            return

        with ctrl.action:
            for i, j in diff.items():
                getattr(ctrl, i).update(getattr(self._model, i), **j)

    def _body(self, current):
        return f"""
            ㄩ Plot Configuration

            {self._body_axes(current)}

            {self._body_tracks(current)}

            {self._body_tags('Blockage', 'statustag')}

            {self._body_tags('Bead', 'beadstatustag')}

            {self._body_hairpins(current)}

            {self._body_orientations(current)}
        """.replace("ㄩ", "#")

    def _body_axes(self, current):
        cols   = {i.key: i for i in COLS if i.label}
        nil    = f'|xxx:{self._theme.none}'
        xaxis  = '|' + '|'.join(
            ':'.join(i)
            for i in sorted(self._model.theme.xaxistag.items(), key = lambda x: x[1])
            if len(current.hairpins) or not cols[i[0]].fit
        ) + '|'

        yaxis = '|' + '|'.join(
            ':'.join(i)
            for i in sorted(
                self._model.theme.yaxistag.items(),
                key = lambda x: '' if x[0] == 'bead' else x[1]
            )
            if len(current.hairpins) or not cols[i[0]].fit
        ) + '|'

        return f"""
            ㄩㄩ Axes

            <b>X-axis</b>                     <b>sort by value</b>
            %(xinfo[0].name){xaxis}           %(xinfo[0].sortbyvalue)b
            %(xinfo[1].name){nil}{xaxis}      %(xinfo[1].sortbyvalue)b
            %(xinfo[2].name){nil}{xaxis}      %(xinfo[2].sortbyvalue)b

            Y-axis                  %(yaxis){yaxis}
            Count normalization     %(norm)|0:all|1:first axis|2:second axis|3:third axis|

            Track denomination      %(tracknames)|full:full|order:number|simple:simple|
            Use label colors        %(uselabelcolors)b
            {"" if current.hairpins else "Stretch factor (µm/bp)    %(stretch).2F"}
            {_JSWidgetVericicator(xaxis, yaxis)()}
        """.strip()

    def _body_tags(self, title: str, attr: str):
        vals = getattr(self._model.theme, attr).values()
        line = f"""
            {{i[1]: <20}}    %({attr}[{{i[0]}}])250s"""
        return (
            f"""
            ㄩㄩ {title.capitalize()} Status
            <b> Rename and regroup labels</b>
            """
            + "".join(line.format(i = i) for i in enumerate(vals))
        )

    @staticmethod
    def _body_hairpins(current):
        if len(current.hairpins) < 2:
            return ""

        line = """
            {i[1]: <20}    %(hairpinsel[{i[0]}])b"""
        return (
            """
            ㄩㄩ Hairpins
            True positives: Δ|blockage - binding| <    %(closest)D

            <b> Check which hairpins to consider</b>
            """
            + "".join(line.format(i = i) for i in enumerate(current.hairpins))
        )

    def _body_orientations(self, current):
        if len(current.hairpins) < 1:
            return ""

        line = """
            {i[1]: <20}    %(orientationsel[{i[0]}])b"""
        return (
            """
            ㄩㄩ Binding Orientation
            <b> Check which binding orientations to consider</b>
            """
            + "".join(
                line.format(i = i)
                for i in enumerate(self._model.theme.orientationtag.values())
            )
        )

    @staticmethod
    def _body_tracks(current):
        if not current.roots:
            return ""

        line = """
            {i}-{j: <20}    %(tracktag[{i}])250s    %(tracksel[{i}])b     %(beadmask[{i}])csvd"""
        return (
            """
            ㄩㄩ Tracks

            !!    Group name    Selected    Discarded beads
            """
            + "".join(line.format(i = i, j = trackname(j)) for i, j in enumerate(current.roots))
        )
