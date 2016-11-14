#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests toolbar """
import time
from flexxutils     import flexxaction # pylint: disable=unused-import
from view.trackplot import TrackPlot   # pylint: disable=no-member,import-error
from view.toolbar   import ToolBar     # pylint: disable=no-member,import-error
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
    print(flexxaction)

def test_trackplot(flexxaction):       # pylint: disable=redefined-outer-name
    u"test plot"
    flexxaction.init('withtoolbar', TrackPlot)
    print(flexxaction.view)
    flexxaction.run(flexxaction.pypress('Ctrl-o'),
                    lambda _: time.sleep(5),
                    #flexxaction.pypress('Ctrl-z'),
                    path = 'small_pickle')
