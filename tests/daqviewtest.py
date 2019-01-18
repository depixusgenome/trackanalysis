#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Testing DAQ view"
from daq.server.simulator   import runfovsimulator
from testutils.bokehtesting import bokehaction  # pylint: disable=unused-import

def test_serverview(bokehaction): # pylint: disable=redefined-outer-name
    "test the view"
    with bokehaction.launch('daq.server.dataview.DAQFoVServerView',
                            'daq.app.default') as server:

        daq  = server.ctrl.daq
        pack = server.ctrl.theme.model("fovmemory").packet
        cnt = [0]

        @daq.observe
        def _onaddfovdata(**_): # pylint: disable=unused-variable
            cnt[0] += pack

        proc, state = runfovsimulator(daq.config.network.fov)
        proc.start()
        server.wait()
        assert cnt[0] == 0
        assert len(daq.data.fov.view()) == cnt[0]

        daq.listen(True, False)
        server.wait()
        state.value = 0
        proc.join()

        assert cnt[0] > 0
        assert len(daq.data.fov.view()) == cnt[0]

if __name__ == '__main__':
    test_serverview(bokehaction(None))
