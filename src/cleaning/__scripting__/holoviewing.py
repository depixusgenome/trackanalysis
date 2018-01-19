#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Provides displays on good and bad beads
"""
from   typing               import List
from   itertools            import product
import pandas               as     pd
import numpy                as     np

from   utils.holoviewing    import hv, addproperty, addto, displayhook, ItemsDisplay
from   model.__scripting__  import Tasks
from   .                    import TrackCleaningScript, TracksDictCleaningScript

@addproperty(TrackCleaningScript)
class TrackCleaningDisplay(ItemsDisplay):
    """
    Display the messages or fixed beads
    """
    def display(self, **_):
        "returns a table of cleaning messages"
        return self._items.messages()

    def fixed(self, **kwa):
        "displays aligned cycles for fixed beads only"
        beads = self._items.fixed(**kwa)
        return self._items.track.apply(Tasks.alignment)[beads,...]

TrackCleaningScript.__doc__ += (
    """
    In **jupyter**, this object automatically displays the list messages.
    """)

@addproperty(TracksDictCleaningScript)    # type: ignore
@displayhook
class CleaningHeatMap:
    """
    Returns a heat map displaying beads versus tracks where colored squares indicates
    the number of bad beads per track or bad tracks per bead.

    Attributes:

    * `tooltip`: the tooltip to be displayed, by default the warnings issued by cleaning.
    * `beads`: the beads to display
    * `forceclean`: get messages even from cleaned tracks
    * `hits` Є {"nbadkeys", "nbadbeads"} indicates whether to sort by bad
    beads or bad tracks
    * `sort` Є {"nbadkeys", "nbadbeads"} indicates whether to sort by bad
    beads or bad tracks
    """
    def __init__(self, itm, **kwa):
        self.items      = itm
        self.beads      = kwa.pop('beads',      None)
        self.forceclean = kwa.pop('forceclean', False)
        self.hits       = kwa.pop('hits',       'nbadbeads')
        self.sort       = kwa.pop('sort',       'nbadkeys')
        self.tooltip    = kwa.pop('tooltip',    '{msg.types}|')
        self.kwa        = kwa

    def __call__(self, **kwa):
        self.__init__(self.items, **kwa)
        return self

    def _messages(self, beads):
        frame = self.items.messages(beads, self.forceclean, **self.kwa)

        # pylint: disable=eval-used
        msg   = lambda i: ''.join(eval('f"'+self.tooltip+'"', dict(msg = j))
                                  for j in i.itertuples())
        return pd.DataFrame({'msg': frame.groupby(['bead', 'key']).apply(msg)})

    @staticmethod
    def _badbeads(new):
        fcn   = lambda x, y: (new
                              .groupby(level = x)
                              .apply(len)
                              .rename(f'nbad{y}s'))
        return (new
                .join(fcn('bead', 'key'))
                .join(fcn('key',  'bead'))
                .groupby(['bead', 'key'])
                .aggregate(dict(nbadkeys = 'min', nbadbeads = 'min', msg = 'sum'))
                .reset_index())

    def _addgoodbeads(self, grp, beads):
        good  = list(set(beads) - set(grp.bead.unique()))
        itr   = lambda: product(self.items.tracks, good)
        nitr  = len(good) * len(self.items.tracks)
        nbadb = dict(grp[['key', 'nbadbeads']])

        return pd.concat([grp, pd.DataFrame({'msg':       [''] * nitr,
                                             'key':       [i for i, _ in itr()],
                                             'bead':      [i for _, i in itr()],
                                             'nbadkeys':  [np.NaN] * nitr,
                                             'nbadbeads': [nbadb.get(i, np.NaN)
                                                           for i, _ in itr()]})])

    def display(self):
        """
        Returns a heat map displaying beads versus tracks where colored squares indicates
        the number of bad beads per track or bad tracks per bead.

        Options:


        * `forceclean`: get messages even from cleaned tracks
        * `hits` Є {"nbadkeys", "nbadbeads"} indicates whether to sort by bad
        beads or bad tracks
        * `sort` Є {"nbadkeys", "nbadbeads"} indicates whether to sort by bad
        beads or bad tracks
        """
        beads = list(self.items.tracks.availablebeads() if self.beads is None else
                     self.beads)
        grp   = self._badbeads(self._messages(beads))
        grp   = self._addgoodbeads(grp, beads)

        vdims = ["nbadkeys", "nbadbeads"]
        if self.sort  == vdims[0]:
            vdims = vdims[::-1]
        grp   = grp.sort_values(vdims)

        if self.hits != vdims[0]:
            vdims = vdims[::-1]

        return (hv.HeatMap(grp, kdims = ['bead', 'key'], vdims = vdims + ['msg'])
                (plot = dict(tools=['hover'])))

TracksDictCleaningScript.__doc__ += (
    """
    In **jupyter**, this object automatically displays a heat map displaying
    beads versus tracks where colored squares indicates the number of bad beads
    per track.
    """)

__all__: List[str] = []
