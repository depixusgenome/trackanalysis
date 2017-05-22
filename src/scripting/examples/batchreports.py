#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"Creating reports"
from itertools                   import repeat
from concurrent.futures          import ProcessPoolExecutor
from peakfinding.reporting.batch import generatereports, PeakFindingBatchTemplate
from data.trackio                import LegacyGRFilesIO

def run(args):
    "creates one report"
    paths, kwa = args
    generatereports(paths, **kwa)
    return paths[0]

def main(trackfiles, grfiles, reports, nprocs = None):
    "main launcher"
    template = PeakFindingBatchTemplate()
    paths    = LegacyGRFilesIO.scan(trackfiles, grfiles)
    itr      = zip(paths[0], repeat(dict(template = template, reporting = reports)))

    print('missing\n', '\n-'.join(str(i) for i in paths[1]))
    print('missing\n', '\n-'.join(str(i) for i in paths[2]))
    with ProcessPoolExecutor(nprocs) as pool:
        for trk in pool.map(run, itr):
            print('done ', trk)

if __name__ == '__main__':
    main("/media/data/sirius/remi/2017-05-*/*.trk",
         "/home/pol/Seafile/Sequencing_Remi/Analysis/Remi_2017-05-*_done/*/",
         "/tmp/reports/*.xlsx")
