#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the status of running jobs"
from copy                import deepcopy
from itertools           import chain
from typing              import Dict, List, Any, Optional
from bokeh.palettes      import all_palettes as _PALETTES  # pylint: disable=no-name-in-module

from data.trackops       import trackname
from modaldialog.button  import ModalDialogButton, DialogButtonConfig
from modaldialog.options import NotTuple
from taskmodel           import RootTask
from ...model            import (
    AxisConfig, BeadsScatterPlotModel, FoVStatsPlotModel, getcolumn, BinnedZ,
    COLS, Slice, INVISIBLE, FoVStatsPlotConfig, NotSet
)
from ._jobsstatus        import hairpinnames

_FILTER_CNV = [
    (("peaks", "peakposition"), 'pkfilter'),
    (("peaks", "baseposition"), 'bpfilter'),
    (("peaks", "closest"),      'bindfilter'),
    (("peaks", "hybridisationrate"), ("konfilter")),
    (("peaks", "averageduration"), ("kofffilter")),
]


class PeakcallingPlotConfig(DialogButtonConfig):
    "configure axes choice"
    def __init__(self):
        super().__init__('peakcalling.view.axes', 'Plotting', icon = 'stats-bars')
        self.none: str = "none"

class PeakcallingPlotModel:     # pylint: disable=too-many-instance-attributes
    "configure xaxis choice"
    def __init__(
            self,
            beads: BeadsScatterPlotModel,
            stats: FoVStatsPlotModel,
            cnf: Optional[PeakcallingPlotConfig] = None
    ):
        if cnf is None:
            cnf = PeakcallingPlotConfig()

        self.hsort:          bool    = 'hairpin' in beads.theme.sorting
        self.tsort:          bool    = 'track' in beads.theme.sorting
        self.bsort:          bool    = 'bead' in beads.theme.sorting
        self.defaultcolors:  str     = stats.theme.defaultcolors
        self.binnedz:        BinnedZ = deepcopy(stats.theme.binnedz)
        self.binnedbp:       BinnedZ = deepcopy(stats.theme.binnedbp)
        self.closest:        int     = stats.theme.closest
        self.stretch:        float   = round(stats.theme.stretch, 2)
        self.uselabelcolors: bool    = stats.theme.uselabelcolors
        self.tracknames:     str     = stats.theme.tracknames
        self.yaxis:          str     = stats.theme.yaxis
        self.xinfo: List[AxisConfig] = [
            AxisConfig('xxx') if i >= len(stats.theme.xinfo) else deepcopy(stats.theme.xinfo[i])
            for i in range(3)
        ]

        procs                            = stats.tasks.processors
        self.roots:      List[RootTask]  = list(procs)
        self.reftrack:   int             = (
            0 if stats.display.reference is None else
            (1 + self.roots.index(stats.display.reference))
        )
        self.beadmask:   List[List[int]] = [
            NotTuple(i) if isinstance(i, NotSet) else tuple(i)
            for i in [stats.display.beads.get(j, set()) for j in procs]
        ]
        self.tracktag:   List[str]       = [stats.display.tracktag.get(i, cnf.none) for i in procs]
        self.tracksel:   List[bool]      = [i not in stats.display.roots for i in procs]
        self.statustag:  List[str]       = list(stats.theme.statustag.values())
        self.beadstatustag:    List[str]       = list(stats.theme.beadstatustag.values())
        self.hairpins:   List[str]       = sorted(hairpinnames(procs))
        self.hairpinsel: List[bool]      = [i not in stats.display.hairpins for i in self.hairpins]
        self.orientationsel: List[bool]  = [
            i not in stats.display.orientations
            for i in stats.theme.orientationtag.keys()
        ]
        self.linear: bool = stats.theme.linear
        if stats.theme.yaxisnorm is not None:
            self.xnorm: str  = '4'
        else:
            self.xnorm = next(
                (
                    str(i+1)
                    for i, j in enumerate(self.xinfo)
                    if not j.norm and j.name != 'xxx'
                ),
                '0'
            )

        self.__dict__.update({j: stats.display.ranges.get(i, Slice()) for i, j in _FILTER_CNV})

    reset = __init__

    def diff(
            self,
            right: 'PeakcallingPlotModel',
            stats: FoVStatsPlotModel
    ) -> Dict[str, Dict[str, Any]]:
        "return a dictionnary of changed items"
        diff: Dict[str, Dict[str, Any]] = {'display': {}, 'theme': {}}
        for i, j, k in chain(
                self.__diff_axes(right),
                self.__diff_top(right),
                self.__diff_filters(right),
                self.__diff_reftrack(right),
                self.__diff_tracks(right),
                self.__diff_hairpins(right),
                self.__diff_orientation(right, stats),
                self.__diff_tags("statustag", right, stats),
                self.__diff_tags("beadstatustag",   right, stats),
                self.__diff_attr(right)
        ):
            diff[i][j] = k
        return diff

    def __diff_top(self, right):
        itms = ('hairpin', 'track', 'bead')
        left = {i for i in itms if getattr(self, f'{i[0]}sort')}
        cur  = {i for i in itms if getattr(right, f'{i[0]}sort')}
        if cur != left:
            yield ('theme', 'sorting', cur)

    def __diff_attr(self, right):
        for i in ('closest', 'stretch', 'uselabelcolors', 'linear'):
            if abs(getattr(self, i) - getattr(right, i)) > 1e-2:
                yield ('theme', i, getattr(right, i))

        right.binnedz.reset(.1)
        right.binnedbp.reset(10)
        for i in ('tracknames', 'binnedz', 'binnedbp', 'defaultcolors'):
            if getattr(self, i) != getattr(right, i):
                yield ('theme', i, getattr(right, i))

    def __diff_filters(self, right: 'PeakcallingPlotModel'):
        empty  = Slice()
        dleft  = {i: getattr(self,  j) for i, j in _FILTER_CNV if i and i != empty}
        dright = {i: getattr(right, j) for i, j in _FILTER_CNV if i and i != empty}
        if dleft != dright:
            yield ('display', 'ranges', dright)

    def __diff_reftrack(self, right: 'PeakcallingPlotModel'):
        iright = int(right.reftrack)
        if self.reftrack != iright:
            yield ('display', 'reference', (self.roots[iright-1] if iright else None))

    def __diff_axes(self, right: 'PeakcallingPlotModel'):
        cpy = deepcopy(right.xinfo)
        for i, j in enumerate(cpy):
            j.norm = right.xnorm == '0' or right.xnorm != str(i+1)

        if self.xnorm == '4' and right.xnorm != '4':
            yield ('theme', 'yaxisnorm', None)
        elif self.xnorm != '4' and right.xnorm == '4':
            yield ('theme', 'yaxisnorm', FoVStatsPlotConfig().yaxisnorm)

        if any(i.__dict__ != j.__dict__ for i, j in zip(self.xinfo, cpy)):
            out = (
                'theme', 'xinfo',
                [
                    j for i, j  in enumerate(cpy)
                    if j.name != 'xxx' and j.name not in {k.name for k in cpy[:i]}
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

        right.beadmask = [
            set() if not j else NotSet(j) if isinstance(j, NotTuple) else set(j)
            for j in right.beadmask
        ]

        if any(i != j for i, j in zip(self.beadmask, right.beadmask)):
            yield (
                'display', 'beads',
                {
                    i: k
                    for i, j, k in zip(right.roots, self.beadmask, right.beadmask or [])
                    if j != k
                }
            )

        if any(i != j for i, j in zip(self.tracktag, right.tracktag)):
            yield ('display', 'tracktag', dict(zip(right.roots, right.tracktag)))

class _JSWidgetVericicator:
    "returns the js code to deal with the modal dialog"
    def __init__(self, hashairpin: bool, xaxis:str, yaxis:str):
        self.hashairpin = hashairpin
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

    def __reset_norm(self) -> str:
        return """
            var el4 = document.getElementsByName("xnorm")[0];
            el4.disabled = true;
            for(i = 1; i < el4.options.length; i++)
            {
                var itm       = el4.options[i];
                if((i-1) < elems.length)
                {
                    itm.innerHTML = elems[i-1].options[elems[i-1].selectedIndex].innerHTML;
                    itm.disabled  = elems[i-1].selectedIndex == 0
                } else {
                    itm.disabled = %s;
                }
                if(itm.disabled) {
                    itm.innerHTML = "none";
                } else if(yaxis.selectedIndex == 0) {
                    el4.disabled = false;
                }
            }
            if((!el4.disabled) && el4.options[el4.selectedIndex].disabled)
                el4.selectedIndex = 0;

            el4.parentElement.parentElement.style.display = yaxis.selectedIndex == 0 ? null: "none";
        """ % ('false' if self.hashairpin else 'true')

class PeakcallingPlotWidget(ModalDialogButton[PeakcallingPlotConfig, PeakcallingPlotModel]):
    "Configure the plot"
    def __init__(self):
        super().__init__()
        self._beads = BeadsScatterPlotModel()
        self._stats = FoVStatsPlotModel()

    def _newmodel(self, ctrl) -> PeakcallingPlotModel:
        return PeakcallingPlotModel(self._beads, self._stats, self._theme)

    def _diff(self, current: PeakcallingPlotModel, changed: PeakcallingPlotModel):
        return current.diff(changed, self._stats)

    def _action(self, ctrl, diff):
        for i, j in diff.items():
            sorting = j.pop('sorting', None)
            getattr(ctrl, i).update(getattr(self._stats, i), **j)
            if sorting is not None:
                ctrl.theme.update(self._beads.theme, sorting = sorting)

    def _body(self, current):
        out = (
            """# Plot Configuration
            """
            + self._body_bottomplot(current)
            + self._body_topplot(current)
            + self._body_tracks(current)
            + self._body_blockage()
            + self._body_tags('Bead', 'beadstatustag')
            + self._body_hairpins(current)
            + self._body_orientations(current)
        ).replace("ㄩ", "#")
        return out

    @staticmethod
    def _body_topplot(current):
        if len(current.hairpins) < 1:
            return ""
        return f"""
            ㄩㄩ Top Plot

            Sort hairpins by fit quality   %(hsort)b
            Sort tracks by fit quality     %(tsort)b
            Sort beads by fit quality      %(bsort)b
        """.strip()

    def _body_bottomplot(self, current):
        cols   = {i.key: i for i in COLS if i.label}
        nil    = f'|xxx:{self._theme.none}'
        xaxis  = '|' + '|'.join(
            ':'.join(i)
            for i in sorted(self._stats.theme.xaxistag.items(), key = lambda x: x[1])
            if len(current.hairpins) or not cols[i[0]].fit
        ) + '|'

        yaxis = '|' + '|'.join(
            ':'.join(i)
            for i in sorted(
                self._stats.theme.yaxistag.items(),
                key = lambda x: '' if x[0] == 'bead' else x[1]
            )
            if len(current.hairpins) or not cols[i[0]].fit
        ) + '|'

        xnorm       = '0:all|1:first|2:second|3:third|4:'+getcolumn('status').label
        palette     = 'none:none|' + '|'.join(f'{i}:{i}' for i in sorted(_PALETTES))
        htmlpalette = "<a href='view/bokeh_palettes.html' target='_blank'>color palette</a>"
        return f"""
            ㄩㄩ Bottom Plot Axes

            <b>X-axis</b>                     <b>sort by value</b>
            %(xinfo[0].name){xaxis}           %(xinfo[0].sortbyvalue)b
            %(xinfo[1].name){nil}{xaxis}      %(xinfo[1].sortbyvalue)b
            %(xinfo[2].name){nil}{xaxis}      %(xinfo[2].sortbyvalue)b

            Y-axis                          %(yaxis){yaxis}
            Count normalization             %(xnorm)|{xnorm}|

            Track denomination          %(tracknames)|full:full|order:number|simple:simple|
            Use label colors            %(uselabelcolors)b
            Default {htmlpalette}       %(defaultcolors)|{palette}|
            Prefer a linear x-axis      %(linear)b
            {"" if current.hairpins else "Stretch factor (µm/bp)    %(stretch).2F"}
            {_JSWidgetVericicator(len(current.hairpins) > 0, xaxis, yaxis)()}
        """

    def _body_blockage(self):
        def _lab(name):
            return getcolumn(name).label
        return self._body_tags('Blockage', 'statustag').replace(
            'Status\n',
            f"""Status & Z
            {getcolumn('binnedz').label} bin width     %(binnedz.width).2F

            ** Mask data not within the following range:**
            %(pkfilter.start).3of   ≤ {_lab('peakposition')} ≤          %(pkfilter.stop).3of
            %(konfilter.start)oF    ≤ {_lab('hybridisationrate')} ≤     %(konfilter.stop)oF
            %(kofffilter.start)oF   ≤ {_lab('averageduration')} ≤       %(kofffilter.stop)oF

            """
        )

    def _body_tags(self, title: str, attr: str):
        vals = getattr(self._stats.theme, attr).values()
        line = f"""
            {{i[1]: <20}}    %({attr}[{{i[0]}}])250s"""
        return (
            f"""
            ㄩㄩ {title.capitalize()} Status
            ** Rename and regroup labels**"""
            + "".join(line.format(i = i) for i in enumerate(vals))
        )

    @staticmethod
    def _body_hairpins(current):
        if len(current.hairpins) < 1:
            return ""

        def _lab(name):
            return getcolumn(name).label

        line = """
            %(hairpinsel[{i[0]}])b   {i[1]: <20}"""
        return (
            f"""
            ㄩㄩ Hairpins
            {getcolumn('binnedbp').label} bin width                %(binnedbp.width)D
            {getcolumn('closest').label}: Δ|blockage - binding| <  %(closest)D

            ** Mask data not within the following ranges:**
            %(bpfilter.start)od     ≤ {_lab('baseposition')} ≤     %(bpfilter.stop)od
            %(bindfilter.start)oD   ≤ {_lab('closest')} ≤          %(bindfilter.stop)oD

            ** Check which hairpins to display**"""
            + "".join(line.format(i = i) for i in enumerate(current.hairpins))
        )

    def _body_orientations(self, current):
        if len(current.hairpins) < 1:
            return ""

        line = """
            %(orientationsel[{i[0]}])b   {i[1]: <20}"""
        return (
            """
            ㄩㄩ Binding Orientation
            ** Check which binding orientations to display**"""
            + "".join(
                line.format(i = i)
                for i in enumerate(self._stats.theme.orientationtag.values())
            )
        )

    @staticmethod
    def _body_tracks(current):
        if not current.roots:
            return ""

        reftrack = '|'.join(
            f"{i+1}:{trackname(j).replace('|', '_')}"
            for i, j in enumerate(current.roots)
        )
        line     = """
            %(tracksel[{i}])b  {i}-{j: <20}  %(tracktag[{i}])250s  %(beadmask[{i}])ocsvι"""
        return (
            f"""
            ㄩㄩ Tracks
            Reference Track     %(reftrack)|0:none|{reftrack}|

            !!    <b>Group</b>  <b>Discarded beads</b>"""
            + "".join(line.format(i = i, j = trackname(j)) for i, j in enumerate(current.roots))
        )
