#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widget for exporting the data"
import asyncio
from pathlib             import Path
from typing              import List
from bokeh.models        import Div, CustomAction, CustomJS
from view.dialog         import FileDialog
from utils.gui           import startfile

class SaveFileDialog(FileDialog):
    "A file dialog that adds a default save path"
    def __init__(self, ctrl):
        super().__init__(ctrl, storage = "save")

        def _defaultpath(ext, bopen):
            assert not bopen
            pot = [i for i in self.storedpaths(ctrl, "load", ext) if i.exists()]
            ope = next((i for i in pot if i.suffix not in ('', '.gr')), None)
            if ope is None:
                ope = self.firstexistingpath(pot)

            pot = self.storedpaths(ctrl, "save", ext)
            sav = self.firstexistingparent(pot)

            if ope is None:
                return sav

            if sav is None:
                if Path(ope).is_dir():
                    return ope
                sav = Path(ope).with_suffix(ext[0][1])
            else:
                psa = Path(sav)
                if psa.suffix == '':
                    sav = (psa/Path(ope).stem).with_suffix(ext[0][1])
                else:
                    sav = (psa.parent/Path(ope).stem).with_suffix(psa.suffix)

            self.defaultextension = sav.suffix[1:] if sav.suffix != '' else None
            return str(sav)

        self.__store   = self.access[1]
        self.access    = _defaultpath, None
        self.filetypes = "xlsx:*.xlsx"
        self.title     = "Export plot data to excel"

    def store(self, *_):
        "store the path"
        return self.__store(*_)

class CSVExporter:
    "exports all to csv"
    @classmethod
    def addtodoc(cls, mainviews, ctrl, doc) -> List[Div]:
        "creates the widget"
        dlg = SaveFileDialog(ctrl)
        div = Div(text = "", width = 0, height = 0)

        mainview = mainviews[0] if isinstance(mainviews, (list, tuple)) else mainviews
        figure   = mainview.getfigure()

        figure.tools = (
            figure.tools
            + [
                CustomAction(
                    action_tooltip = dlg.title,
                    callback       = CustomJS(
                        code = 'div.text = div.text + " ";',
                        args = dict(div = div)
                    )
                )
            ]
        )

        if isinstance(mainviews, (list, tuple)):
            for i in mainviews[1:]:
                i.getfigure().tools = i.getfigure().tools + [figure.tools[-1]]

        def _cb(attr, old, new):
            if new != "":
                div.text = ""
                asyncio.create_task(cls._run(dlg, mainview, ctrl, doc))

        div.on_change("text", _cb)
        return [div]

    def reset(self, *_):
        "reset all"

    @staticmethod
    async def _run(dlg: SaveFileDialog, mainview, ctrl, doc):
        paths = await mainview.threadmethod(dlg.save)
        if paths is None:
            return

        @doc.add_next_tick_callback
        def _toolbarsave():
            with ctrl.action:
                dlg.store(paths, False)  # pylint: disable=not-callable
                path = paths if isinstance(paths, (str, Path)) else paths[0]
                if mainview.export(path) and Path(path).exists():
                    startfile(path)
