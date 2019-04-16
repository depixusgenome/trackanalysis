#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Tests data """
from data.trackio import MuWellsFilesIO
from tests.testingcore import path as utpath

def test_muwells(tmp_path):
    "test muwells data"
    assert MuWellsFilesIO.instrumenttype({}) == "muwells"
    paths = MuWellsFilesIO.check((
        utpath("W6N46_HPB20190107_OR134689_cycle_1.9-2.10_TC10m.txt"),
        utpath("W6N46_HPB20190107_W2_OR134689_cycle_1.9-2.10_TC10m.trk"),
    ))
    assert paths

    output = MuWellsFilesIO.open(paths)
    assert output['phases'].shape == (32, 8)
    assert output['sequencelength'] == {0: None}
    assert abs(output['experimentallength'][0] - 31.720950927734293) < 1e-5

    with open(utpath("W6N46_HPB20190107_OR134689_cycle_1.9-2.10_TC10m.txt")) as istr:
        with open(tmp_path/"lio.txt", "w") as ostr:
            for _ in range(4):
                print(istr.readline().strip(), file = ostr)
            for _ in range(output['phases'][4,5]):
                istr.readline()
            for _ in range(output['phases'][4,5], output['phases'][-5,2]):
                print(istr.readline().strip(), file = ostr)


    paths = MuWellsFilesIO.check((
        utpath("W6N46_HPB20190107_W2_OR134689_cycle_1.9-2.10_TC10m.trk"),
        tmp_path/"lio.txt",
    ))
    output2 = MuWellsFilesIO.open(paths)
    assert output2['phases'].shape == (22, 8)

if __name__ == '__main__':
    from  pathlib import Path
    test_muwells(Path("/tmp/"))
