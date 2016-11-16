#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests toolbar """
from pytest         import approx                   # pylint: disable=no-name-in-module
from flexx          import event
from flexxutils     import flexxaction              # pylint: disable=unused-import
from view.trackplot import TrackPlot, BeadPlotter   # pylint: disable=no-member,import-error
from view.toolbar   import ToolBar                  # pylint: disable=no-member,import-error
from testdata       import path

def test_toolbar(flexxaction):                      # pylint: disable=redefined-outer-name
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
    def _printrng(fact):
        dico  = fact.ctrl.getGlobal(BeadPlotter.key("current"))
        valx.append(dico.get("x"))
        valy.append(dico.get("y"))

    flexxaction.init('withtoolbar', _TrackPlotTest)
    flexxaction.run(flexxaction.pypress('Ctrl-o'),
                    flexxaction.jspress(' '),                _printrng,
                    flexxaction.jspress('Shift-ArrowUp'),    _printrng,
                    flexxaction.jspress('Shift-ArrowRight'), _printrng,
                    flexxaction.jspress('ArrowLeft'),        _printrng,
                    flexxaction.jspress('ArrowUp'),          _printrng,
                    flexxaction.jspress('ArrowRight'),       _printrng,
                    flexxaction.jspress('ArrowDown'),        _printrng,
                    flexxaction.jspress('Shift-ArrowLeft'),  _printrng,
                    flexxaction.jspress('Shift-ArrowDown'),  _printrng,
                    flexxaction.jspress('Shift-ArrowUp'),    _printrng,
                    flexxaction.jspress('Shift-ArrowRight'), _printrng,
                    flexxaction.jspress(' '),                _printrng,
                    flexxaction.pypress('Ctrl-z'),
                    path = 'small_legacy')

    for i in range(2):
        for j in (-4, -1):
            assert valx[0][i] == approx(valx[j][i])
            assert valy[0][i] == approx(valy[j][i])
        assert valx[0][i] == approx(valx[1][i])
        assert valx[3][i] == approx(valx[4][i])
        assert valx[2][i] == approx(valx[5][i])
        assert valx[2][i] == approx(valx[6][i])

        assert valy[1][i] == approx(valy[2][i])
        assert valy[1][i] == approx(valy[3][i])
        assert valy[4][i] == approx(valy[5][i])
        assert valy[1][i] == approx(valy[6][i])
