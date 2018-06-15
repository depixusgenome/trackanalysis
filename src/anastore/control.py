#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Sets things up for the taskcontroller"

from tempfile        import mkstemp
from pathlib         import Path
from typing          import Tuple, Union

from control.taskio  import TaskIO
from utils           import initdefaults
from utils.logconfig import getLogger

from .api            import dump, load

LOGS = getLogger(__name__)

class AnaIO(TaskIO):
    "Ana IO"
    EXT = ('ana',)
    def open(self, path:Union[str, Tuple[str,...]], model:tuple): # type: ignore
        "opens an ana file"
        if isinstance(path, tuple):
            if len(path) != 1:
                return None
            path = path[0]

        out = load(path)
        if out is not None and len(model):
            raise NotImplementedError()
        if out is not None:
            LOGS.info(f'{type(self).__name__} loading {path}')
        return [out] if isinstance(out, dict) else out

    def save(self, path:str, models):
        "closes an ana file"
        if len(models):
            LOGS.info('%s saving %s', type(self).__name__, path)
            dump(models, path)
        else:
            raise IOError("Nothing to save", "warning")
        return True

class ConfigAnaIOConfig:
    "define how to save the json data"
    name         = "anaio"
    indent       = 4
    ensure_ascii = False
    sort_keys    = True
    @initdefaults(frozenset(locals()) - {'name'})
    def __init__(self, **_):
        pass

class ConfigAnaIO(AnaIO):
    "Ana IO"
    EXT = ('ana',)
    _model: ConfigAnaIOConfig
    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        self._ctrl  = ctrl
        self._model = ctrl.theme.add(ConfigAnaIOConfig(), False)

    def open(self, path:Union[str, Tuple[str,...]], model:tuple): # type: ignore
        "opens an ana file"
        out = super().open(path, model)
        if not out:
            return None

        if isinstance(out, list) and len(out) == 1 and isinstance(out[0], dict):
            out = out[0]
            seq = out.pop('sequence', {})
            if 'path' in seq and not Path(seq['path']).exists():
                seq.pop("path")

            if 'sequences' in seq and 'path' not in seq:
                seq['path'] = mkstemp()[1]
                with open(seq['path'], "w") as stream:
                    for i, j in seq['sequences'].items():
                        print(f"> {i}", file = stream)
                        print(j, file = stream)

            elif 'path' in seq and 'sequences' not in seq:
                try:
                    import sequences
                    seq['sequences'] = dict(sequences.read(seq['path']))
                except: # pylint: disable=bare-except
                    seq.pop('path')

            if seq:
                def _fcn(model = None,  **_2):
                    if model[0] is out['tasks'][0][0]:
                        self._ctrl.theme.update("sequence", **seq)
                self._ctrl.tasks.oneshot("opentrack", _fcn)
        return out['tasks']

    def save(self, path:str, models):
        "closes an ana file"
        curr   = self._ctrl.display.get("tasks", "roottask")
        models = [i for i in models if curr is i[0]]

        if len(models):
            cnf = self._ctrl.theme.getconfig("sequence").maps[0]
            cnf.pop('history', None)
            dump(dict(tasks = models, sequence = cnf), path, **self._model.__dict__)
        else:
            raise IOError("Nothing to save", "warning")
        return True
