#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"Creating reports"
from itertools                   import repeat
from concurrent.futures          import ProcessPoolExecutor
from peakfinding.reporting.batch import generatereports, PeakFindingBatchTemplate
from data.trackio                import LegacyGRFilesIO
from utils.logconfig             import getLogger, logToFile
import version
LOGS = getLogger()

def run(args):
    "creates one report"
    paths, kwa = args
    generatereports(paths, **kwa)
    return paths[0]

def main(trackfiles, grfiles, reports, nprocs = None):
    "main launcher"
    logToFile(reports.replace("*.xlsx", "log.txt"), backupCount = 1)
    LOGS.info("Starting:\n- trk: %s\n- gr: %s\n- reports: %s",
              trackfiles, grfiles, reports)
    LOGS.info("Version: %s\n", version.version())

    template = PeakFindingBatchTemplate()
    def _match(trk, grf):
        if 'ramp' in trk.stem:
            return False
        return len(set(trk.stem.split('_'))-set(grf.stem.split('_'))) == 1

    paths    = LegacyGRFilesIO.scan(trackfiles, grfiles, matchfcn = _match)
    itr      = zip(paths[0], repeat(dict(template = template, reporting = reports)))

    if len(paths[1]):
        LOGS.warning('missing its gr files\n\t%s', '\n\t'.join(str(i) for i in paths[1]))
    if len(paths[2]):
        LOGS.warning('missing its track file\n\t%s', '\n\t'.join(str(i) for i in paths[2]))

    if nprocs <= 1:
        for args in itr:
            trk = run(args)
            LOGS.info('done %s', trk)

    else:
        with ProcessPoolExecutor(nprocs) as pool:
            for trk in pool.map(run, itr):
                LOGS.info('done %s', trk)
    return None

if __name__ == '__main__':
    # pylint: disable=line-too-long
    #main("/media/samba-mount/sirius/remi/2017-05-*/*.trk",
    #     "/home/dev/Seafile/Sequencing_Remi/Analysis/Remi_2017-05-*/*/",
    #     "reports/*.xlsx")
    main("/media/samba-mount/sirius/sylwia/2017-05-*/*.trk",
         "/home/dev/Seafile/Sequencing_Sylwia/clean_cgr_projects--main_folder/BNA_3mers_037HP_SDA/**/*.cgr",
         "reports/*.xlsx")
