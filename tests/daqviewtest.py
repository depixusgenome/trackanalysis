#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Testing DAQ view"
from daq.serversimulator      import runserversimulator

def test_serverview(bokehaction):
    "test the view"
    with bokehaction.launch('daq.serverview.DAQFoVServerView',
                            'daq.app.default') as server:

        daq = server.ctrl.daq

        cnt = [0]
        @daq.observe
        def _onaddfovdata(**_): # pylint: disable=unused-variable
            cnt[0] += 1

        proc = runserversimulator(daq.config.network.fov)
        proc.start()
        server.wait()
        proc.terminate()

        assert len(daq.data.fov) == cnt[0] * daq.config.network.fov.packet

if __name__ == '__main__':
    from testingcore.bokehtesting import bokehaction as _
    test_serverview(_(None))
