#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests toolbar """
import time
from pytest         import approx       # pylint: disable=no-name-in-module
from flexx          import event
from flexxutils     import flexxaction  # pylint: disable=unused-import
from view.trackplot import TrackPlot    # pylint: disable=no-member,import-error
from view.toolbar   import ToolBar      # pylint: disable=no-member,import-error
from testdata       import path

def test_toolbar(flexxaction):         # pylint: disable=redefined-outer-name
    u"tests that the menubar works"
    def _checknone(fact):
        curr = fact.ctrl.getGlobal('current')
        fact.asserts(len(fact.box.children) == 3)
        fact.asserts(curr.get('track', default = None) is None)
        fact.asserts(curr.get('task',  default = None) is None)

    def _checkopen(fact):
        curr  = fact.ctrl.getGlobal('current')
        track = curr.get('track')
        fact.asserts(len(fact.box.children) == 4)
        fact.asserts(track.path  == path('small_legacy'))
        fact.asserts(track is curr.get('task'))
        fact.asserts(fact.ctrl.getGlobal('config', 'last.path.trk') == track.path,
                     (fact.ctrl.getGlobal('config', 'last.path.trk'), track.path))

    flexxaction.init('default', ToolBar)
    flexxaction.run(_checknone,
                    flexxaction.pypress('Ctrl-o'), _checkopen,
                    flexxaction.pypress('Ctrl-z'), _checknone,
                    flexxaction.pypress('Ctrl-y'), _checkopen,
                    path = 'small_legacy')
    flexxaction.test(14)

def test_trackplot(flexxaction):        # pylint: disable=redefined-outer-name
    u"test plot"
    class _TrackPlotTest(TrackPlot):    # pylint: disable=too-many-ancestors
        # pylint: disable=no-self-use
        @event.emitter
        def _keys_(self, val = '')-> dict:
            return {'value': val}

        class JS:                       # pylint: disable=no-member,missing-docstring
            @event.connect("_keys_")
            def _onkeypress(self, *events):
                self.children[0].node.children[0].onkeydown(events[-1]['value'])

    valx = []
    valy = []
    vals = []
    flexxaction.init('withtoolbar', _TrackPlotTest)
    def _printrng(**evts):
        if 'x' in evts:
            valx.append(evts['x'].value)
        if 'y' in evts:
            valy.append(evts['y'].value)
        vals.append((valx[-1], valy[-1]))
    flexxaction.ctrl.observe("globals.current.plot.bead", _printrng)

    flexxaction.run(flexxaction.pypress('Ctrl-o'),
                    lambda _: time.sleep(2),
                    flexxaction.jspress(' '),
                    flexxaction.jspress('Shift-ArrowUp'),
                    flexxaction.jspress('Shift-ArrowRight'),
                    flexxaction.jspress('ArrowLeft'),
                    flexxaction.jspress('ArrowUp'),
                    flexxaction.jspress('ArrowRight'),
                    flexxaction.jspress('ArrowDown'),
                    flexxaction.jspress('Shift-ArrowLeft'),
                    flexxaction.jspress('Shift-ArrowDown'),
                    flexxaction.jspress('Shift-ArrowUp'),
                    flexxaction.jspress('Shift-ArrowRight'),
                    flexxaction.jspress(' '),
                    flexxaction.pypress('Ctrl-z'),
                    path = 'small_legacy')

    truths = (((650.515,  1152.485),    (-0.0489966, 1.1207037013)),
              ((650.515,  1152.485),    (0.18494344, 0.8867636370)),
              ((750.909,  1052.091),    (0.18494344, 0.8867636370)),
              ((690.6726, 991.8546),   (0.18494344, 0.8867636370)),
              ((690.6726, 991.8546),   (0.32530748, 1.0271276756)),
              ((750.909,  1052.091),    (0.32530748, 1.0271276756)),
              ((750.909,  1052.091),    (0.18494344, 0.8867636370)),
              ((650.515,  1152.485),    (0.18494344, 0.8867636370)),
              ((650.515,  1152.485),    (-0.0489966, 1.1207037013)),
              ((650.515,  1152.485),    (0.18494344, 0.8867636370)),
              ((750.909,  1052.091),    (0.18494344, 0.8867636370)),
              ((650.515,  1152.485),    (-0.0489966, 1.1207037013)))

    assert len(truths) == len(vals)
    for i, truth1 in enumerate(truths):
        for j, truth2 in enumerate(truth1):
            for k, truth3 in enumerate(truth2):
                assert vals[i][j][k] == approx(truth3)
