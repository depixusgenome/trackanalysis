#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"stuff for running all beads"
from   asyncio                  import sleep as _sleep
from   functools                import partial
from   multiprocessing          import Process, Pipe

import numpy                    as     np

from view.base                  import spawn
from ._processors               import runbead

class JobConfig:
    "JobConfig"
    def __init__(self):
        self.name:     str   = "hybridstat.precomputations"
        self.ncpu:     int   = 2
        self.waittime: float = .1

class JobDisplay:
    "JobConfig"
    def __init__(self):
        self.name:     str  = "hybridstat.precomputations"
        self.calls:    int  = 1
        self.canstart: bool = False

class JobRunner:
    "Deals with pool computations"
    def __init__(self, mdl):
        self._mdl     = mdl
        self._config  = JobConfig()
        self._display = JobDisplay()

    def swapmodels(self, ctrl):
        "swap models for those in the controller"
        self._config  = ctrl.theme.swapmodels(self._config)
        self._display = ctrl.display.swapmodels(self._display)

    def observe(self, ctrl):
        "sets observers"

        @ctrl.display.hashwith(self._display)
        def _start(calllater = None, **_):
            disp = self._display
            if not disp.canstart:
                return

            ctrl.display.update(disp, calls = disp.calls+1)

            @calllater.append
            def _poolcompute():
                with ctrl.display("hybridstat.peaks.store", args = {}) as sendevt:
                    self._poolcompute(sendevt, disp.calls)

        @ctrl.display.observe("tasks")
        @ctrl.display.hashwith(self._display)
        def _onchangetrack(old = None, calllater = None, **_):
            if "taskcache" in old:
                _start(calllater)

        @ctrl.display.observe(self._display)
        @ctrl.display.hashwith(self._display)
        def _onprecompute(calllater = None, old = None, **_):
            if {"canstart"} == set(old):
                _start(calllater)

        ctrl.tasks.observe("addtask", "updatetask", "removetask", _start)

    @staticmethod
    def _poolrun(pipe, procs, refcache, keys):
        for bead in keys:
            out = runbead(procs, bead, refcache)
            pipe.send((bead, out, refcache.get(bead, None)))
            if pipe.poll():
                return
        pipe.send((None, None, None))

    def _keepgoing(self, cache, root, idtag):
        calls = self._display.calls
        return root is self._mdl.roottask and calls == idtag and cache() is not None

    def _poolcompute(self, sendevt, identity, **_):  # pylint: disable=too-many-locals
        if (
                self._config.ncpu <= 0
                or not self._display.canstart
                or identity != self._display.calls
        ):
            return

        mdl   = self._mdl
        root  = mdl.roottask
        procs = mdl.processors()
        if procs is None:
            return

        store     = procs.data.setcachedefault(-1, {})
        cache     = procs.data.getcache(-1)
        procs     = procs.cleancopy()
        refc      = mdl.fittoreference.refcache
        keepgoing = partial(self._keepgoing, cache, root, identity)

        keys  = np.array(list(set(mdl.track.beads.keys()) - set(store)))
        nkeys = len(keys)
        if not nkeys:
            return

        async def _iter():
            pipes = []
            ncpu  = min(nkeys, self._config.ncpu)
            for job in range(0, nkeys, nkeys//ncpu+1):
                inp, oup = Pipe()
                args     = (oup, procs, refc, keys[job:job+nkeys//ncpu+1])
                Process(target = self._poolrun, args = args).start()
                pipes.append(inp)

            while len(pipes) and keepgoing():
                await _sleep(self._config.waittime)
                for i, inp in list(enumerate(pipes))[::-1]:
                    while inp.poll() and keepgoing():
                        out = inp.recv()
                        if out[0] is None:
                            del pipes[i]
                            break

                        elif out[0] not in store:
                            yield out

            for inp in pipes:
                inp.send(True)

        async def _thread():
            sendevt({"bead": None, "check": keepgoing})
            async for bead, itms, ref in _iter():  # pylint: disable=not-an-iterable
                store[bead] = itms
                if ref is not None:
                    refc[bead] = ref
                sendevt({"bead": bead, "check": keepgoing})

        spawn(_thread)
