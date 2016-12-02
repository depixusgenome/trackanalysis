#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests toolbar
from pytest         import approx       # pylint: disable=no-name-in-module
from flexxutils     import flexxaction  # pylint: disable=unused-import
from view.trackplot import TrackPlot    # pylint: disable=no-member,import-error
from view.toolbar   import ToolBar      # pylint: disable=no-member,import-error
from testdata       import path

def _test_toolbar(flexxaction):         # pylint: disable=redefined-outer-name
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
                    'Py-Control-o', _checkopen,
                    'Py-Control-z', _checknone,
                    'Py-Control-y', _checkopen,
                    path = 'small_legacy')
    flexxaction.test(14)

def test_trackplot(flexxaction):        # pylint: disable=redefined-outer-name
    u"test plot"
    valx = []
    valy = []
    vals = []
    def _printrng(**evts):
        if 'x' in evts:
            valx.append(evts['x'].value)
        if 'y' in evts:
            valy.append(evts['y'].value)
        vals.append((valx[-1], valy[-1]))

    def _get():
        return self.children[0].node.children[0] # pylint: disable=undefined-variable

    flexxaction.init('withtoolbar', TrackPlot, _get)
    flexxaction.ctrl.observe("globals.current.plot.bead", _printrng)

    flexxaction.run('Py-Control-o',        flexxaction.sleep(2),
                    'Js- ',             'Js-Shift-ArrowUp',    'Js-Shift-ArrowRight',
                    'Js-ArrowLeft',     'Js-ArrowUp',          'Js-ArrowRight',
                    'Js-ArrowDown',     'Js-Shift-ArrowLeft',  'Js-Shift-ArrowDown',
                    'Js-Shift-ArrowUp', 'Js-Shift-ArrowRight', 'Js- ',
                    'Py-Control-z',        path = 'small_legacy')

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
    assert vals == approx(truths)
"""
