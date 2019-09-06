#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A simple GUI for accessing files
"""
from   pathlib import Path
import os

import holoviews     as hv
import panel         as pn
import panel.widgets as pnw

from .tracksdict import TracksDict
from .track      import Track

class TrackSelector:
    "GUI for selecting tracks and creating a TracksDict"
    _col: pn.Column

    def __init__(self, defaultpath = "./**/*.trk"):
        self.paths    = pnw.TextInput(name = "Path",  value = defaultpath, width = 600)
        self.match    = pnw.TextInput(name = "Match", width = 200)
        self.selector = pnw.Select(name = "Track", width = 850)
        self.pane     = pn.Pane(hv.Div(""), width = 850)

        self.paths.param.watch(self._on_update, "value")
        self.match.param.watch(self._on_update, "value")
        self.selector.param.watch(self._on_newtracks, "value")

    @property
    def track(self) -> Track:
        "Return the current tracksdict"
        return Track(path = self.selector.value)

    def display(self) -> pn.Column:
        "create the view"
        self._col = pn.Column(pn.Row(self.paths, self.match), self.selector, self.pane)
        self._on_update()
        return self._col

    def _on_update(self, *_):
        "update the options"
        parts = Path(self.paths.value).parts
        ind   = next((i for i, j in enumerate(parts) if '*' in j), len(parts))
        root  = Path(os.path.sep.join(parts[:ind]))
        patt  = os.path.sep.join(parts[ind:]) if ind < len(parts) else '*.trk'

        if self.match.value:
            self.selector.options = sorted(
                str(i.path if isinstance(i.path, (str, Path)) else i.path[0])
                for i in TracksDict(str(root/patt), match = self.match.value).values()
            )
        else:
            self.selector.options = sorted(root.glob(patt))

        self.selector.value = (
            self.selector.value if self.selector.value in self.selector.options else
            next(iter(self.selector.options), "")
        )
        self._on_newtracks()

    def _on_newtracks(self, *_):
        "update the values"
        if not self.selector.value:
            beads = []
        else:
            track = self.track
            beads = list(track.beads.keys())

        if beads:
            self._col[-1] = self._new_display(track, beads)
        else:
            self._col[-1] = pn.Pane(hv.Div("No track or no beads"))

    @staticmethod
    def _new_display(track, beads):
        sel  = pnw.Select(
            name    = "Plot",
            value   = "cleancycles",
            options = ["cleanbeads", "cleancycles", "cycles", "peaks"]
        )
        lst  = pnw.DiscreteSlider(name = "Beads", value = beads[0], options = beads)
        pane = pn.Pane(hv.Div("No track or no beads"))

        def _show(_):
            dmap = getattr(track, sel.value).display.display()
            pane.object = dmap[lst.value]

        lst.param.watch(_show, "value")
        sel.param.watch(_show, "value")
        col = pn.Column(pn.Row(lst, sel), pane)
        _show(None)
        return col

class TracksDictSelector:
    "GUI for selecting tracks and creating a TracksDict"
    _col: pn.Column

    def __init__(self, defaultpath = "./**/*.trk"):
        self.paths    = pnw.TextInput(name = "Path",  value = defaultpath, width = 600)
        self.match    = pnw.TextInput(name = "Match",        width = 200)
        self.selector = pnw.CrossSelector(name = "selector", width = 850)
        self.pane     = pn.Pane(hv.Div(""), width = 850)

        self.paths.param.watch(self._on_update, "value")
        self.match.param.watch(self._on_update, "value")
        self.selector.param.watch(self._on_newtracks, "value")

    @property
    def tracksdict(self) -> TracksDict:
        "Return the current tracksdict"
        return TracksDict.leastcommonkeys(self.selector.value)

    def display(self) -> pn.Column:
        "create the view"
        self._on_update()
        return pn.Column(pn.Row(self.paths, self.match), self.selector, self.pane)

    def _on_update(self, *_):
        "update the options"
        parts = Path(self.paths.value).parts
        ind   = next((i for i, j in enumerate(parts) if '*' in j), len(parts))
        root  = Path(os.path.sep.join(parts[:ind]))
        patt  = os.path.sep.join(parts[ind:]) if ind < len(parts) else '*.trk'

        if self.match.value:
            self.selector.options = sorted(
                str(i.path if isinstance(i.path, (str, Path)) else i.path[0])
                for i in TracksDict(str(root/patt), match = self.match.value).values()
            )
        else:
            self.selector.options = sorted(root.glob(patt))

        self.selector.value = sorted(set(self.selector.value) & set(self.selector.options))
        self._on_newtracks()

    def _on_newtracks(self, *_):
        "update the values"
        if not self.selector.value:
            self._col[-1] = pn.Pane(hv.Div("No tracks selected"))
            return

        self._col[-1] = self._new_display(self.tracksdict)

    @staticmethod
    def _new_display(tracks):
        "update the values"
        return pn.Pane(
            hv.Table(tracks.dataframe().assign(path = lambda x: x.path.apply(str)))
        )

def displaytrack(fcn) -> TrackSelector:
    "creates a new TrackSelector child class, changing the _on_newtracks method"
    cls = TrackSelector
    return type(f'New{cls.__name__}', (cls,), {'_new_display': staticmethod(fcn)}).display()

def displaytracksdict(fcn) -> TracksDictSelector:
    "creates a new TrackSelector child class, changing the _on_newtracks method"
    cls = TracksDictSelector
    return type(f'New{cls.__name__}', (cls,), {'_new_display': staticmethod(fcn)}).display()
