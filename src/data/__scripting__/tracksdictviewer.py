#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A simple GUI for accessing files
"""
from   abc      import abstractmethod
from   typing   import TypeVar, Generic, Type
from   pathlib  import Path

import holoviews     as hv
import panel         as pn
import panel.widgets as pnw

from  utils.inspection import templateattribute
from  utils.gui        import relativepath
from .tracksdict       import TracksDict
from .track            import Track

Item     = TypeVar("Item", Track, TracksDict)
Selector = TypeVar("Selector", pnw.Select, pnw.CrossSelector)


class _BasePathSelector(Generic[Item, Selector]):
    "GUI for selecting tracks and creating a TracksDict"
    _col:  pn.Column
    _root: Path

    def __init__(self, defaultpath = "./**/*.trk"):
        self.paths    = pnw.TextInput(name = "Path",  value = defaultpath, width = 600)
        self.match    = pnw.TextInput(name = "Match", width = 200)
        self.selector = templateattribute(self, 1)(name = "Track", width = 850)

        self.paths.param.watch(self._on_update, "value")
        self.match.param.watch(self._on_update, "value")
        self.selector.param.watch(self._on_newtracks, "value")

    def display(self) -> pn.Column:
        "create the view"
        self._col = pn.Column(pn.Row(self.paths, self.match), self.selector, pn.Pane(hv.Div("")))
        self._on_update()
        return self._col

    def _on_update(self, *_):
        "update the options"
        parts = Path(self.paths.value).parts
        ind   = next((i for i, j in enumerate(parts) if '*' in j), len(parts))
        root  = Path().joinpath(*parts[:ind])
        patt  = str(Path().joinpath(*parts[ind:])) if ind < len(parts) else '*.trk'

        if self.match.value:
            options = (
                str(i.path if isinstance(i.path, (str, Path)) else i.path[0])
                for i in TracksDict(str(root/patt), match = self.match.value).values()
            )
        else:
            options = (root.glob(patt))

        self._root, self.selector.options = relativepath(options)
        if isinstance(self.selector, pnw.CrossSelector):
            self.selector.value = sorted(set(self.selector.value) & set(self.selector.options))
        else:
            self.selector.value = (
                self.selector.value if self.selector.value in self.selector.options else
                next(iter(self.selector.options), "")
            )
        self._on_newtracks()

    def _on_newtracks(self, *_):
        "update the values"
        if not self.selector.value:
            self._col[-1] = pn.Pane(hv.Div("No tracks selected"))
            return

        obj = self._new_display()
        if obj is not None:
            self._col[-1] = obj

    @abstractmethod
    def _new_display(self):
        pass

class TrackSelector(_BasePathSelector[Track, pnw.Select]):
    "GUI for selecting tracks and creating a TracksDict"
    @property
    def track(self) -> Track:
        "Return the current tracksdict"
        return Track(path = self._root/self.selector.value)

    def _new_display(self):
        track = self.track
        beads = list(track.beads.keys())
        if not beads:
            return pn.Pane("No beads in this track")

        sel  = pnw.Select(
            name    = "Plot",
            value   = "cleancycles",
            options = ["cleanbeads", "cleancycles", "cycles", "peaks"]
        )
        lst  = pnw.DiscreteSlider(name = "Beads", value = beads[0], options = beads)
        pane = pn.Pane(hv.Div(""))

        def _show(_):
            dmap = getattr(track, sel.value).display.display()
            pane.object = dmap[lst.value]

        lst.param.watch(_show, "value")
        sel.param.watch(_show, "value")
        col = pn.Column(pn.Row(lst, sel), pane)
        _show(None)
        return col

class TracksDictSelector(_BasePathSelector[TracksDict, pnw.CrossSelector]):
    "GUI for selecting tracks and creating a TracksDict"
    @property
    def tracksdict(self) -> TracksDict:
        "Return the current tracksdict"
        return TracksDict.leastcommonkeys([self._root/i for i in self.selector.value])

    def _on_newtracks(self, *_):
        "update the values"
        dframe = hv.Table(self.tracksdict.dataframe().assign(path = lambda x: x.path.apply(str)))
        self._col[-1].object = dframe

def displaytrack(fcn = None) -> TrackSelector:
    "creates a new TrackSelector child class, changing the _on_newtracks method"
    cls: Type[TrackSelector] = TrackSelector
    if fcn is not None:
        cls = type(f'New{cls.__name__}', (cls,), {'_new_display': fcn})
    return cls().display()

def displaytracksdict(fcn = None) -> TracksDictSelector:
    "creates a new TrackSelector child class, changing the _on_newtracks method"
    cls: Type[TracksDictSelector] = TracksDictSelector
    if fcn is not None:
        cls = type(f'New{cls.__name__}', (cls,), {'_new_display': fcn})
    return cls().display()
