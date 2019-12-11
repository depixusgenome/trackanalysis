#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Provides access to currently cached jobs"
from datetime                   import datetime
from pathlib                    import Path
from typing                     import (
    Tuple, Optional, Type, ClassVar, Iterator, List, cast
)
import time

import numpy as np

from bokeh.io                   import curdoc

from cleaning.processor         import FixedBeadDetectionTask, BeadSubtractionTask
from eventdetection.processor   import ExtremumAlignmentTask, EventDetectionTask
from eventdetection.view        import ALIGN_LABELS
from modaldialog.button         import ModalDialogButton, DialogButtonConfig
from peakfinding.processor      import PeakSelectorTask
from taskmodel                  import Task, RootTask
from taskmodel.dataframe        import DataFrameTask
from ...processor.__config__    import FitToHairpinTask
from ...model                   import TasksModelController, keytobytes

_TTIP:  str = "<{cls} aria-label='{ttip}' data-balloon-pos='{pos}' data-balloon-length='{size}'>"
_BREAK: str = "&#10;"

def _tooltip(msg, classtype = 'div', pos = 'down', size = 'xlarge') -> str:
    if isinstance(msg, (tuple, list)):
        msg = _BREAK.join(str(i) for i in msg)
    out = _TTIP.format(cls = classtype, ttip = msg, pos = pos, size = size)
    return (out[:-1] + ' data-balloon-break>') if _BREAK in out else out


class StorageExplorerConfig(DialogButtonConfig):
    "storage config"
    def __init__(self):
        super().__init__('peakcalling.view.storage.explorer', 'Storage', icon = 'download2')
        self.machines = [
            "sirius", "helicon", "vega", "sdi_beta_1", "rosalind", "george", "francis"
        ]
        self.date        = "%Y-%m-%d %H:%M"
        self.splits      = [7*86400, 14*86400]
        self.splitlabels = ['≤ 1 week', '≥ 1 week', '≥ 2 weeks']

class _Store:       # pylint: disable=too-many-instance-attributes
    def __init__(self, existing, roots, key, val):
        self.loaded:    bool               = key in existing
        self.discard:   bool               = False
        self.trackdate: float              = val['trackdate']
        self.statsdate: float              = val['statsdate']
        self.path:      str                = val['path']
        self.model:     Tuple[Task,...]    = val['model']
        self.fit:       bool               = any(
            isinstance(i, FitToHairpinTask) for i in val['model']
        )
        self.root:      Optional[RootTask] = None if not self.loaded else roots[existing.index(key)]

class StorageExplorerModel:
    "current info"
    def __init__(self, mdl):
        procs                    = mdl.tasks.processors
        self.cacheduration: int  = mdl.diskcache.duration // 86400    # duration in days
        self.cachesize:     int  = mdl.diskcache.maxsize  // 1000000  # size in Mb
        self.ncpu:          int  = mdl.jobs.config.ncpu
        self.cachereset:    bool = False
        if procs:
            self.withfit:       bool = any(
                any(isinstance(j, FitToHairpinTask) for j in i.model) for i in procs.values()
            )
        else:
            self.withfit = True

        if self.cachesize > 0:
            existing   = [keytobytes(i.model) for i in procs.values()]
            roots      = list(procs)
            self.items = sorted(
                (
                    _Store(existing, roots, key, val)
                    for key, val in list(mdl.diskcache.iterkeys(parse = True))
                    if val['good']
                ),
                key = lambda x: (not x.loaded, -x.statsdate)
            )
        else:
            self.items = []

    def diff(self, changed):
        "yield the changes"
        info = dict(self.__diff_diskcache(changed))
        lst  = [
            (data.model if data.loaded else data.root)
            for data, cur in zip(changed.items, self.items)
            if data.loaded != cur.loaded
        ]
        return (lst, info) if lst or info else ()

    def __diff_diskcache(self, right):
        if self.ncpu != right.ncpu:
            yield ('ncpu', right.ncpu)
        if self.cachesize != right.cachesize:
            yield ('maxsize', right.cachesize * 1000000)
        if self.cacheduration != right.cacheduration:
            yield ('duration', max(0.9, right.cacheduration) * 86400)
        if self.cachereset != right.cachereset:
            yield ('reset', right.cachereset)
        if any(i.discard for i in right.items):
            yield ("processors", [i.model for i in right.items if i.discard])

class StorageExplorer(ModalDialogButton[StorageExplorerConfig, StorageExplorerModel]):
    "explore current storage"
    __STYLE:   ClassVar[str] = "style='display:block;text-align:center'"
    __DISCARD: ClassVar[str] = (
        "<div style='filter:hue-rotate(250deg)'> %(items[{ind}].discard)b </div>"
    )
    __TITLES:  ClassVar[Tuple[str,...]]  = (
        "Load", "Analyzed", "File", "Machine", "Created", "Hairpin", "Discard"
    )

    def __init__(self):
        super().__init__()
        self._model = TasksModelController()

    def runifnothingloaded(self, ctrl, doc):
        "run if no processors are available"
        if len(self._model.tasks.processors) == 0:
            if doc is None:
                doc = curdoc()
            self.run(ctrl, doc)

    def _body(self, current: StorageExplorerModel) -> str:
        unkn    = f'<div {self.__STYLE}>?</div>'
        out     = f"""
            # Disk Cache
        """
        titles  = "  ".join("<b "+self.__STYLE+">"+i+"</b>" for i in self.__TITLES)
        if current.cachesize > 0:
            for withfit in (current.withfit, not current.withfit):
                items   = [(i, j) for i, j in enumerate(current.items) if j.fit is withfit]
                if not items:
                    continue

                out    += f"""
                    ## With{"" if withfit else "out"} Hairpins

                """
                for btn, elems in self.__body_split(items):
                    out += btn.strip() + "\n" + titles + "\n"
                    for ind, info in elems:
                        out  += (
                            "       "
                            + "  ".join((
                                f"%(items[{ind}].loaded)b",
                                datetime.fromtimestamp(info.statsdate).strftime(self._theme.date),
                                self.__body_path(info),
                                str(next(
                                    (i for i in self._theme.machines if i in info.path),
                                    unkn
                                )),
                                datetime.fromtimestamp(info.trackdate).strftime(self._theme.date),
                                self.__body_fit(info),
                                self.__DISCARD.format(ind = ind)
                            ))
                            + "\n"
                        )
                    out += "\n"

        out += """
            ## Cache Settings

            Number of CPUs              %(ncpu)D
            Max cache size (Mb)         %(cachesize)D
            Expires in (days)           %(cacheduration)D
            Reset current tracks        %(cachereset)b
            """
        return out

    def _newmodel(self, ctrl) -> StorageExplorerModel:
        return StorageExplorerModel(self._model)

    _DISCARDED: Tuple[Type[Task], ...] = (FixedBeadDetectionTask, DataFrameTask)

    def _action(self, ctrl, diff):
        for data in diff[0]:
            if isinstance(data, RootTask):
                ctrl.tasks.closetrack(cast(RootTask, data))
            else:
                ctrl.tasks.opentrack(model = tuple(
                    i for i in data if not isinstance(i, self._DISCARDED)
                ))

        # do this last as it might delete the cache
        self._model.updatediskcache(ctrl, **diff[1])

    def __body_split(
            self, items: List[Tuple[int, _Store]]
    ) -> Iterator[Tuple[str, List[Tuple[int, _Store]]]]:
        grps: List[List[Tuple[int, _Store]]] = [[] for _ in self._theme.splitlabels]
        dates                                = np.array([*self._theme.splits])[::-1]
        now                                  = time.time()
        for i, j  in zip(items, np.searchsorted(dates, [now-i[1].statsdate for i in items])):
            grps[j].append(i)

        if sum(len(i) > 0 for i in grps) == 1:
            yield ('', items)
            return

        first = True
        for k, j in zip(self._theme.splitlabels, grps):
            if len(j):
                yield (("▼ " if first else "▶ ") + k, j)
                first = False

    @classmethod
    def __body_path(cls, info):

        def _get(tpe):
            return next((i for i in info.model if isinstance(i, tpe)), None)

        ttip  = (
            info.path,
            "Subtracted beads: " + ', '.join(
                str(i) for i in getattr(_get(BeadSubtractionTask), 'beads', [])
            ),
            "Blockage min duration: %d"   % _get(EventDetectionTask).events.select.minlength,
            "Alignment: %s"  % ALIGN_LABELS[getattr(_get(ExtremumAlignmentTask), 'phase', None)],
            'Peak min blockage count: %d' % _get(PeakSelectorTask).finder.grouper.mincount,
        )
        return _tooltip(ttip) + Path(info.path).stem + "</div>"

    @classmethod
    def __body_fit(cls, info):
        task = next((i for i in info.model if isinstance(i, FitToHairpinTask)), None)
        return (
            f'<div {cls.__STYLE}>no</div>' if not info.fit else
            (
                _tooltip(
                    (
                        "Oligos: "   + ', '.join(task.oligos),
                        "Hairpins: " + (
                            ', '.join(task.sequences) if isinstance(task.sequences, dict) else
                            str(task.sequences)
                        )
                    ),
                    classtype = "i"
                )
                + "yes </i>"
            )
        )
