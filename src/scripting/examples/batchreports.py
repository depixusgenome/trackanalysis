#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"Creating reports"
from itertools                   import repeat
from concurrent.futures          import ProcessPoolExecutor
from peakfinding.reporting.batch import generatereports, PeakFindingBatchTemplate
from data.trackio                import LegacyGRFilesIO
from utils.logconfig             import getLogger, logToFile
LOGS = getLogger()

def run(args):
    "creates one report"
    paths, kwa = args
    generatereports(paths, **kwa)
    return paths[0]

def main(trackfiles, grfiles, reports, nprocs = None):
    "main launcher"
    logToFile(reports.replace("*.xlsx", "log.txt"), backupCount = 1)
    LOGS.info("Starting:\n- trk: %s\n- gr: %s\n- reports: %s\n",
              trackfiles, grfiles, reports)

    template = PeakFindingBatchTemplate()
    paths    = LegacyGRFilesIO.scan(trackfiles, grfiles)
    itr      = zip(paths[0], repeat(dict(template = template, reporting = reports)))

    if len(paths[1]):
        LOGS.warning('missing its gr files\n\t'+'\n\t'.join(str(i) for i in paths[1]))
    if len(paths[2]):
        LOGS.warning('missing its track file\n\t'+'\n\t'.join(str(i) for i in paths[2]))
    with ProcessPoolExecutor(nprocs) as pool:
        for trk in pool.map(run, itr):
            LOGS.info('done %s', trk)

if __name__ == '__main__':
    main("/media/samba-mount/sirius/remi/2017-05-*/*.trk",
         "/home/dev/Seafile/Sequencing_Remi/Analysis/Remi_2017-05-*_done/*/",
         "reports/*.xlsx")
