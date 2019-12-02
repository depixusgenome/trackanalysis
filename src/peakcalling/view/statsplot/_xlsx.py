#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"export xlsx data"

from   typing                  import Dict, List, Tuple, Any

import pandas as pd

import version
from   data.trackops           import trackname
from   taskstore               import dumps

class XlsxReport:
    "export to xlsx"
    @classmethod
    def export(cls, plotter, path) -> bool:
        "export to xlsx"
        info = cls.dataframes(plotter)
        # pylint: disable=abstract-class-instantiated
        with pd.ExcelWriter(str(path), mode='w') as writer:
            for j, k in info:
                j.to_excel(writer, index = False, **k)

        return True

    @classmethod
    def dataframes(cls, plotter):
        "return the figure"
        mdl     = getattr(plotter, '_model')
        plotfcn = getattr(plotter, '_createplot')
        procs   = mdl.tasks.processors.values()

        info    = cls._export_plot(mdl, plotfcn(True), procs, {'bead': 'Bead status'})
        info.extend(cls._export_plot(mdl, plotfcn(False), procs, {}))
        info.extend(cls._export_git())
        info.extend(cls._export_tracks(procs))
        return info

    @staticmethod
    def _export_git() -> List[Tuple[pd.DataFrame, Dict[str, Any]]]:
        itms = [
            ("GIT Version:",      version.version()),
            ("GIT Hash:",         version.lasthash()),
            ("GIT Date:",         version.hashdate())
        ]
        return [(
            pd.DataFrame(dict(
                key   = [i for i, _ in itms],
                value = [j for _, j in itms],
            )),
            dict(header = False, sheet_name = "Tracks")
        )]

    @staticmethod
    def _export_tracks(processors) -> List[Tuple[pd.DataFrame, Dict[str, Any]]]:
        tracks = pd.DataFrame(dict(
            trackid = list(range(len(processors))),
            track   = [trackname(i.model[0]) for i in processors],
            tasks   = [
                dumps(j.model, ensure_ascii = False, indent = 4, sort_keys = True)
                for j in processors
            ]
        ))
        return [(
            tracks, dict(startrow = 5, sheet_name = "Tracks", freeze_panes = (5, len(tracks)))
        )]

    @staticmethod
    def _export_plot(
            mdl, plot, processors, sheetnames
    ) -> List[Tuple[pd.DataFrame, Dict[str, Any]]]:
        plot.compute()
        tracks   = {id(i.model[0]): trackname(i.model[0]) for i in processors}
        trackids = {id(j.model[0]): i for i, j  in enumerate(processors)}
        cnv      = dict(mdl.theme.xaxistag, **mdl.theme.yaxistag)
        cnv.pop('bead')

        info: List[Tuple[pd.DataFrame, Dict[str, Any]]] = []
        for name in ('bead', 'peak'):
            sheet = getattr(plot, f'_{name}', None)
            if not isinstance(sheet, pd.DataFrame):
                continue

            info.append((
                (
                    sheet
                    .assign(
                        track   = sheet.trackid.apply(tracks.__getitem__),
                        trackid = sheet.trackid.apply(trackids.__getitem__)
                    )
                ),
                dict(
                    header       = [cnv.get(k, k) for k in sheet.columns],
                    sheet_name   = sheetnames.get(name, f"{name.capitalize()} statistics"),
                    freeze_panes = (1, len(sheet))
                )
            ))
        return info
