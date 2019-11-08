#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the status of running jobs"
import datetime
from typing              import Tuple, Optional, Type, cast

from cleaning.processor  import FixedBeadDetectionTask
from taskmodel           import Task, RootTask
from taskmodel.dataframe import DataFrameTask
from modaldialog.button  import ModalDialogButton, DialogButtonConfig
from .._model            import TasksModelController, keytobytes


class StorageExplorerConfig(DialogButtonConfig):
    "storage config"
    def __init__(self):
        super().__init__('peakcalling.view.storage.explorer', 'Storage', icon = 'download2')
        self.machines = [
            "sirius", "helicon", "vega", "sdi_beta_1", "rosalind", "george", "francis"
        ]
        self.date     = "%Y-%m-%d %H:%M"

class _Store:       # pylint: disable=too-many-instance-attributes
    def __init__(self, existing, roots, key, val):
        self.loaded:    bool               = key in existing
        self.discard:   bool               = False
        self.trackdate: float              = val['trackdate']
        self.statsdate: float              = val['statsdate']
        self.path:      str                = val['path']
        self.title:     str                = val['title']
        self.model:     Tuple[Task,...]    = val['model']
        self.fit:       bool               = val['fit']
        self.root:      Optional[RootTask] = None if not self.loaded else roots[existing.index(key)]

class StorageExplorerModel:
    "current info"
    def __init__(self, mdl):
        self.cacheduration: int  = mdl.diskcache.duration // 86400    # duration in days
        self.cachesize:     int  = mdl.diskcache.maxsize  // 1000000  # size in Mb
        self.cachereset:    bool = False

        if self.cachesize > 0:
            procs      = mdl.processors
            existing   = [keytobytes(i.model) for i in procs.values()]
            roots      = list(procs)
            self.items = sorted(
                (
                    _Store(existing, roots, key, val)
                    for key, val in list(mdl.diskcache.iterkeys(parse = True))
                ),
                key = lambda x: -x.statsdate
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
    def __init__(self):
        super().__init__()
        self._model = TasksModelController()

    def _body(self, current: StorageExplorerModel) -> str:
        out  = f"""
            # Disk Cache
        """

        if current.cachesize > 0 and len(current.items):
            titles = "Load", "Date", "Machine", "File", "Hairpin", "Discard"
            style  = "style='display:block;text-align:center'"
            unkn   = f'<div {style}>?</div>'
            out   += f"""
                ## Currently Available

                {"  ".join("<b "+style+">"+i+"</b>" for i in titles)}
            """
            for ind, info in enumerate(current.items):
                title = (
                    f"<div data-balloon='{info.path}' data-balloon-pos='down' "
                    f"data-balloon-length='xlarge'>{info.title}</div>"
                )
                out += (
                    "       "
                    + "  ".join((
                        f"%(items[{ind}].loaded)b",
                        datetime.datetime.fromtimestamp(info.trackdate).strftime(self._theme.date),
                        str(next((i for i in self._theme.machines if i in info.path), unkn)),
                        title,
                        f'<i {style}>yes</i>' if info.fit else f'<div {style}>no</div>',
                        f"<div style='filter:hue-rotate(250deg)'> %(items[{ind}].discard)b </div>"
                    ))
                    + "\n"
                )

        out += """
            ## Cache Settings

            Max cache size (Mb)         %(cachesize)D
            Expires in (days)           %(cacheduration)D
            Reset                       %(cachereset)b
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
