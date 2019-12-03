#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Allow setting task info for all jobs"
from copy                   import copy, deepcopy
from typing                 import Optional, Generic, TypeVar, List, Tuple, Dict, cast
from pathlib                import Path

from cleaning.names                      import NAMES
from cleaning.processor.__config__       import BeadSubtractionTask, DataCleaningTask
from data.trackops                       import trackname
from data.trackio                        import TrackIOError
from eventdetection.view                 import ALIGN_LABELS
from eventdetection.processor.__config__ import EventDetectionTask, ExtremumAlignmentTask
from modaldialog.button                  import ModalDialogButton, DialogButtonConfig
from peakfinding.processor.__config__    import PeakSelectorTask
from sequences                           import read as _read
from taskmodel                           import Task, RootTask
from taskmodel.application               import TasksDisplay
from utils.inspection                    import diffobj, templateattribute
from ...processor                        import FitToHairpinTask
from ...model                            import TasksModel

TASK = TypeVar("TASK", bound = Task)


class TaskExplorerConfig(DialogButtonConfig):
    "storage config"
    def __init__(self):
        super().__init__('peakcalling.view.tasks.explorer', 'Settings', icon = 'cog')

class TaskExplorerModel:
    "current info"
    def __init__(self, mdl: TasksModel):
        self.mdl   = mdl
        self.items = [
            _Store(i, j, mdl) for i, j in enumerate(mdl.tasks.tasks.values())
        ]

    def table(self, title: str, *args, **kwa) -> str:
        "return the table for a given attribute"
        return ('\n' + ' '*8).join((
            '## ' + title,
            *(j.line(*args, **kwa) for i, j in enumerate(self.items))
        ))

    def diff(self, cur: RootTask, roots: List[RootTask], changed: 'TaskExplorerModel'):
        "yield the changes"
        info   = {}
        for name in ('probes', 'sequences'):
            itms = dict(getattr(self.mdl.state, name))
            itms.update({i: j for i, j in (getattr(k, name)(roots) for k in changed.items) if j})
            if itms != getattr(self.mdl.state, name):
                info[name] = itms

        itms = dict(self.mdl.state.sequencepaths)
        itms.update({i: j for i, j in (k.sequencepath(roots) for k in changed.items) if j})
        if itms != self.mdl.state.sequencepaths:
            info['paths'] = itms

        if info:
            yield ('control', ('display', 'sequence'), info)

            info = {i: j[cur] for i, j in info.items() if cur in j}
            if 'paths' in info:
                info['path'] = info.pop('paths')
            if info:
                yield ('control', ('theme', 'sequence'), info)

        for i, j in zip(self.items, changed.items):
            yield from i.diff(roots, j)

class TaskExplorer(ModalDialogButton[TaskExplorerConfig, TaskExplorerModel]):
    "explore current storage"
    def __init__(self):
        super().__init__()
        self._model = TasksModel()
        self._curr  = TasksDisplay()

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        super().swapmodels(ctrl)
        self._curr = ctrl.display.swapmodels(self._curr)

    def _diff(self, current: TaskExplorerModel, changed: TaskExplorerModel):
        return list(current.diff(self._curr.roottask, list(self._model.roots), changed))

    def _body(self, current: TaskExplorerModel) -> str:
        return  f"""
            # Computation Settings
            {_Store.tabs(current)}
        """

    def _newmodel(self, ctrl) -> TaskExplorerModel:
        return TaskExplorerModel(self._model)

    def _action(self, ctrl, diff):
        for root, task, other in diff:
            if root == 'control':
                getattr(ctrl, task[0]).update(task[1], **other)
            elif isinstance(other, dict) and other:
                ctrl.tasks.updatetask(root, ctrl.tasks.task(root, type(task)), **other)
            elif other is True:
                ctrl.tasks.addtask(root, task, index = 'auto')
            elif other is False:
                ctrl.tasks.removetask(root, ctrl.tasks.task(root, type(task)))
            else:
                assert other is None or isinstance(other, dict)

class _TaskStore(Generic[TASK]):
    task: Optional[TASK]
    has:  bool
    _ATTR = _TITLE = _TYPE = ''

    def __init__(self, procs, mdl):
        task      = templateattribute(self, 0)
        name      = task.__name__.lower()[:-len('task')]
        self.task = mdl.config[mdl.config.instrument][name]
        self.has  = False
        if procs is not None:
            cur = deepcopy(next((i for i in procs.model if isinstance(i, task)), None))
            if cur:
                self.task = cur
                self.has  = True
            else:
                try:
                    instr = next(iter(procs.run())).track.instrument['type']
                except TrackIOError:
                    pass
                else:
                    self.task = mdl.config[instr][name]

    @classmethod
    def name(cls) -> str:
        "return the name of the attribute in _Store"
        return cls.__name__[1:-len('Store')].lower()

    @classmethod
    def tabs(cls, current) -> str:
        "return the tabs"
        if not (cls._ATTR and cls._TYPE and cls._TITLE):
            raise NotImplementedError()

        name = cls.name() + '.task.' + cls._ATTR
        return f"""
            {current.table(cls._TITLE, name, cls._TYPE)}
        """

    def diff(self, root, changed):
        "yield the changes"
        if self.task is None or self.task == changed.task:
            return

        task, diff = self._diff(root, changed)
        if diff is None:
            return

        yield (root, self.task if self.has else task, diff)

    @classmethod
    def _get(cls, itm, first = False):
        if not cls._ATTR:
            raise NotImplementedError()

        task = itm.task
        for i in cls._ATTR.split('.'):
            task = getattr(task, i)
            if first:
                return {cls._ATTR[:cls._ATTR.find('.')]: task}
        return task

    def _diff(self, _, changed):
        "yield the changes"
        if self._get(self) != self._get(changed):
            return (self.task, self._get(changed, True))
        return None, None

class _SubStore(_TaskStore[BeadSubtractionTask]):
    task: BeadSubtractionTask
    _ATTR  = 'beads'
    _TITLE = 'Subtracted beads'
    _TYPE  = 'ocsvd'

    def _diff(self, _, changed):
        "yield the changes"
        right = sorted(set(changed.task.beads)) if changed.task.beads else []
        left  = sorted(set(self.task.beads))
        if left == right:
            return None, None

        changed.task.beads = right
        return (
            changed.task,
            (
                False if not right    else
                True  if not self.has else
                {'beads': right}
            )
        )

class _CleanStore(_TaskStore[DataCleaningTask]):
    task: DataCleaningTask

    @staticmethod
    def tabs(current) -> str:
        "return the tabs"
        extents = current.table(
            NAMES['extent'],
            'clean.task.minextent',         '.3F',
            '< ' + NAMES['extent'] + ' <',  None,
            'clean.task.maxextent',         '.3F'
        )
        titles = [
            NAMES['population'] + ' <i>Lower Limit</i>',
            NAMES['saturation'] + ' <i>Upper Limit</i>',
        ]
        return f"""
            {extents}
            {current.table(titles[0], 'clean.task.minpopulation', 'D')}
            {current.table(titles[1], 'clean.task.maxsaturation', 'D')}
        """

    def _diff(self, _, changed):
        "yield the changes"
        if not self.has:
            return (changed.task, True)
        return (changed.task, diffobj(changed.task.config(), self.task.config()) or None)

class _EvtStore(_TaskStore[EventDetectionTask]):
    task: EventDetectionTask
    _ATTR  = 'events.select.minlength'
    _TITLE = 'Blockage Min Duration'
    _TYPE  = 'D'

class _AlignStore(_TaskStore[ExtremumAlignmentTask]):
    task: ExtremumAlignmentTask
    __ORDER = tuple(ALIGN_LABELS)

    def __init__(self, *args, **kwa):
        super().__init__(*args, **kwa)
        self.phase = self.__ORDER.index(self.task.phase)

    @classmethod
    def tabs(cls, current) -> str:
        "return the tabs"
        tpe = '|' + '|'.join(f'{i}:{j}' for i, j in enumerate(ALIGN_LABELS.values())) + '|'
        return f"""
            {current.table('Cycle Alignment', 'align.phase', tpe)}
        """

    def diff(self, root, changed):
        "yield the changes"
        changed.phase = int(changed.phase)
        if self.task is None or self.phase == changed.phase:
            return

        changed.task.phase = self.__ORDER[changed.phase]
        yield (
            root,
            self.task if self.has else changed.task,
            (
                False if changed.phase == 0 else
                True  if self.phase == 0    else
                {'phase': changed.task.phase}
            )
        )

class _PeakStore(_TaskStore[PeakSelectorTask]):
    task: PeakSelectorTask
    _ATTR  = 'finder.grouper.mincount'
    _TITLE = 'Peak Min Blockage Count'
    _TYPE  = 'D'

class _FitStore(_TaskStore[FitToHairpinTask]):
    task: FitToHairpinTask

    def __init__(self, procs, mdl):
        super().__init__(procs, mdl)
        self.task = deepcopy(self.task)
        if not self.has:
            self.task.oligos = mdl.state.probes.get(procs.model[0], [])

        if isinstance(self.task.oligos, (list, tuple)):
            self.task.oligos = ', '.join(sorted(self.task.oligos))

        paths = mdl.state.sequencepaths
        root  = procs.model[0]
        if (
                isinstance(self.task.sequences, dict)
                and root in paths
                and self.task.sequences == mdl.state.sequences.get(root, {})
        ):
            self.task.sequences = paths[root]

        # remove items such that a resolve can renew the data
        self.task.fit   = {i: j for i, j in self.task.fit.items()   if i is None}
        self.task.match = {i: j for i, j in self.task.match.items() if i is None}

    @staticmethod
    def tabs(current) -> str:
        "return the tabs"
        return f"""
            {current.table('Hairpins', 'fit.task.sequences', '400s')}
            {current.table('Oligos', 'fit.task.oligos', '400s')}
        """

    def sequences(self, root) -> Tuple[RootTask, Dict[str, str]]:
        "return the sequences for this root task"
        path = self.sequencepath(root)[1]
        return (root, dict(_read(path)) if path else {})

    def sequencepath(self, root) -> Tuple[RootTask, str]:
        "return the sequence path for this root task"
        seq = self.task.sequences
        if isinstance(seq, (str, Path)) and seq and Path(seq).exists():
            return (root, str(seq))
        return (root, "")

    def probes(self, root) -> Tuple[RootTask, List[str]]:
        "return the probe for this root task"
        oligos = self.resolvedtask(root).oligos
        oligos = (
            [oligos] if isinstance(oligos, str) else
            []       if oligos is None else
            list(oligos)
        )
        return (root, oligos)

    def resolvedtask(self, root) -> FitToHairpinTask:
        "return the resolved for this root task"
        txt = self.task.sequences
        if isinstance(txt, str) and '{' in txt:
            itr = (
                (k.replace("'", "").replace('"', '').strip() for k in i.split(':'))
                for i in txt[txt.find('{')+1:txt.rfind('}')].split(',')
            )
            self.task.sequences = {i: j for i, j in itr if j}
        elif isinstance(txt, (Path, str)) and not Path(txt).exists():
            self.task.sequences = None

        if not self.task.oligos:
            self.task.oligos = None
        if not self.task.sequences:
            self.task.sequences = None

        if self.task.sequences and self.task.oligos:
            cpy       = copy(self.task)
            cpy.fit   = {i: j for i, j in self.task.fit.items() if i is None}
            cpy.match = {i: j for i, j in self.task.match.items() if i is None}
            return cpy.resolve(root.path)
        return self.task

    def _diff(self, root, changed):
        "yield the changes"
        left, right = self.task, changed.task
        if (left.sequences == right.sequences) and (left.oligos == right.oligos):
            return None, None

        right, left = changed.resolvedtask(root), self.resolvedtask(root)
        if (left.sequences == right.sequences) and (left.oligos == right.oligos):
            return None, None

        return (
            right,
            (
                False if not (set(right.fit) - {None}) else
                True  if not self.has                  else
                {i: getattr(right, i) for i in ('sequences', 'oligos', 'fit', 'match')}
            )
        )

class _Store:
    ind:  Optional[int]
    name: str
    fit:  _FitStore
    _TASKS = _SubStore, _CleanStore, _EvtStore, _AlignStore, _PeakStore, _FitStore

    def __init__(self, ind, procs, mdl):
        self.__dict__.update({i.name(): i(procs, mdl) for i in self._TASKS})

        self.ind   = ind                                  if procs else None
        self.name  = f"{ind}-{trackname(procs.model[0])}" if procs else "all"

    def line(self, *args, disable = False) -> str:
        "return a new body line"
        line = self.name
        for attr, val in  ((args[i], args[i+1]) for i in range(0, len(args), 2)):
            if val is None:
                line += f'  {attr}'
            else:
                if disable and not getattr(self, attr[:attr.find('.')]).has:
                    attr += '{ disabled=true }'
                line += f'  %(items[{self.ind}].{attr}){val}'
        return line

    def sequences(self, roots) -> Tuple[RootTask, Dict[str, str]]:
        "return the sequences for this root task"
        return self.fit.sequences(roots[self.ind])

    def sequencepath(self, roots) -> Tuple[RootTask, str]:
        "return the sequence path for this root task"
        return self.fit.sequencepath(roots[self.ind])

    def probes(self, roots) -> Tuple[RootTask, List[str]]:
        "return the probe for this root task"
        return self.fit.probes(roots[self.ind])

    def diff(self, roots, changed):
        "yield the changes"
        for i, j in self.__dict__.items():
            if callable(getattr(j, 'diff', None)):
                yield from j.diff(roots[self.ind], getattr(changed, i))

    @classmethod
    def tabs(cls, current) -> str:
        "return the tabs"
        return ('\n' + ' '*8).join(cast(_TaskStore, i).tabs(current) for i in cls._TASKS)
