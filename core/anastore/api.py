#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Track Analysis inputs and outputs.

This does not include track files io.
"""
from   typing       import Union, IO, Any, Optional, cast, Dict
from   contextlib   import closing
from   pathlib      import Path
import json
import io

from ._fromjson import Runner as _InputRunner
from ._tojson   import Runner as _OutputRunner

# pylint: disable=unused-import
from ._patches  import modifyclasses, modifykeys, DELETE, RESET, Patches
from ._utils    import TPE, CNT

PATCHES: Dict[str, Patches] = {}
def _apply(info, patch, patchfcn, inout):
    if patch not in PATCHES:
        return inout()(info)
    patch = PATCHES[patch]
    return inout()(getattr(patch, patchfcn)(info))

def _extractfromxlsx(path: Union[str, Path], sheet = 'summary', entry = 'config:', **_
                    ) -> Optional[IO]:
    """
    Extracts the configuration from an xlxs report.

    Whithin the file, only the sheet `sheet` is considered.  The field to the
    right of the first cell containing `entry` is expected to hold the text to
    be parsed by `anastore`.
    """
    if not isinstance(path, (Path, str)):
        return None

    if Path(path).suffix != '.xlsx':
        return None

    try:
        from openpyxl import load_workbook
    except ImportError:
        return None

    with closing(load_workbook(path, read_only = True)) as book:
        # pylint: disable=not-an-iterable
        rows = next((i.rows for i in book if sheet is None or i.title.lower() == sheet),
                    ())
        txt  = next((str(i[j+1].value)  for i in rows for j, k in enumerate(i)
                     if str(k.value).lower().replace(' ', '') == entry),
                    None)

    return io.StringIO(txt) if txt else None

def _extractfromtext(path: Union[str, Path], **_) -> Optional[IO]:
    """
    Extracts the configuration from an xlxs report.

    Whithin the file, only the sheet `sheet` is considered.  The field to the
    right of the first cell containing `entry` is expected to hold the text to
    be parsed by `anastore`.
    """
    if not isinstance(path, (Path, str)):
        return None

    if isana(path):
        return open(path, 'r', encoding = 'utf-8')
    return None

_EXTRACTORS = (('fromxlsx', _extractfromxlsx), (None, _extractfromtext))

def dumps(info:Any, patch = 'tasks', saveall = False, **kwa):
    u"Dumps data to json. This includes the version number"
    runner = lambda: _OutputRunner(saveall = saveall)
    return json.dumps(_apply(info, patch, 'dumps', runner), **kwa)

def dump(info:Any, path:Union[str,Path,IO], patch = 'tasks', saveall = False, **kwa):
    u"Dumps data to json file. This includes the version number"
    if isinstance(path, (Path, str)):
        with open(str(Path(path).absolute()), 'w', encoding = 'utf-8') as stream:
            return dump(info, stream, patch = patch, saveall = saveall, **kwa)
    runner = lambda: _OutputRunner(saveall = saveall)
    return json.dump(_apply(info, patch, 'dumps', runner), path, **kwa)

def loads(stream:str, patch = 'tasks', **kwa):
    u"Dumps data to json. This includes the version number"
    return _apply(json.loads(stream, **kwa), patch, 'loads', _InputRunner)

def load(path:Union[str,Path,IO], patch = 'tasks', fromxlsx = False, **kwa):
    u"Dumps data to json file. This includes the version number"
    stream = None
    cpy    = dict(kwa)
    cpy.update(fromxlsx = fromxlsx)
    for key, fcn in _EXTRACTORS:
        if not cpy.get(cast(str, key), key is None):
            continue

        stream = fcn(path, **kwa) # type: ignore
        if stream is not None:
            break

    out = None
    if stream:
        with closing(stream):
            out = _apply(json.load(stream, **kwa), patch, 'loads', _InputRunner)
    return out

def isana(path: Union[str, Path]):
    u"Wether the file as an analysis file"
    path = Path(path)
    if not path.is_file():
        return False

    const = '[{"version":'
    try:
        with open(path, 'r', encoding = 'utf-8') as stream:
            line = stream.read(100).replace('\n', '').replace(' ', '')
            return line[:len(const)] == const
    except UnicodeError:
        return False
    except IOError:
        return False

def version(patch):
    u"returns the current version"
    return None if patch not in PATCHES else 'v%d' % PATCHES[patch].version

def iterversions(patch):
    u"iters over possible versions"
    if patch not in PATCHES:
        yield None
    else:
        for i in range(PATCHES[patch].version, -1, -1):
            yield 'v%d' % i
