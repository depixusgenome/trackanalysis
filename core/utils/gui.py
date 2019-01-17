#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"gui related utils"

import re
import sys
import os
import subprocess
from   pathlib     import Path
from   functools   import wraps
from   inspect     import ismethod as _ismeth, isfunction as _isfunc, getmembers
from   enum        import Enum
from   typing      import Set, Union, Optional, Sequence, Dict, cast

import numpy       as     np
from   .inspection import ismethod
from   .logconfig  import getLogger

LOGS = getLogger(__name__)

def coffee(apath: Union[str,Path], name:Optional[str] = None, **kwa) -> str:
    u"returns the javascript implementation code"
    path = Path(apath)
    if name is not None:
        path = path.parent / name # type: ignore

    src = Path(path.with_suffix(".coffee")).read_text()
    for title, val in kwa.items():
        src = src.replace("$$"+title, val)
    return src.replace('$$', '')

def storedjavascript(inpt, name):
    "get stored javascript"
    from bokeh.util import compiler
    cache = getattr(compiler, "_bundle_cache")
    force = False
    for path in Path(inpt).glob("*.js"):
        with open(Path(inpt)/path.name, encoding = 'utf-8') as stream:
            out = stream.readlines()
        key = out[0][len("/*KEY="):-len("*/\n")]
        if key.lower() == name.lower():
            cache[compiler.calc_cache_key()] = "".join(out[1:])
            force                            = True
        else:
            cache[key] = "".join(out[1:])

    key = compiler.calc_cache_key()
    if key not in cache or force:
        output = (Path(inpt)/name).with_suffix('.js')
        string = compiler.bundle_all_models()
        string = f"/*KEY={key}*/\n"+string
        LOGS.info('caching bokeh js to %s', output)
        with open(output, "w", encoding = 'utf-8') as stream:
            print(string, file=stream)

def implementation(apath, *args, extra = None, **kwa):
    "returns the coffeescript implementation"
    path = Path(apath).with_suffix('.coffee')
    if not path.exists():
        # Should only happen with the JS compiler hack
        LOGS.debug('%s was not implemented', path)
        return ""

    code = ''.join(open(path))
    for title, val in kwa.items():
        code = code.replace(title, val)
    for title, val in args:
        code = code.replace(title, val)
    code += "\n"

    if extra:
        code += '\n'+''.join(open(Path(extra).with_suffix('.coffee')))
    return code

class MetaMixin(type):
    u"""
    Mixes base classes together.

    Mixin classes are actually composed. That way there are fewer name conflicts
    """
    def __new__(mcs, clsname, bases, nspace, **kw):
        mixins = kw['mixins']
        def setMixins(self, instances = None, initargs = None):
            u"sets-up composed mixins"
            for base in mixins:
                name =  base.__name__.lower()
                if instances is not None and name in instances:
                    setattr(self, name, instances[name])
                elif getattr(self, name, None) is None:
                    if initargs is not None:
                        setattr(self, name, base(**initargs))
                    else:
                        setattr(self, name, base())

        nspace['setMixins'] = setMixins

        def getMixin(self, base):
            u"returns the mixin associated with a class"
            return getattr(self, base.__name__.lower(), None)

        nspace['getMixin'] = getMixin

        init = nspace.get('__init__', lambda *_1, **_2: None)
        def __init__(self, **kwa):
            init(self, **kwa)
            for base in bases:
                base.__init__(self, **kwa)
            self.setMixins(mixins, initargs = kwa)

        nspace['__init__'] = __init__
        nspace.update(mcs.__addaccesses(mixins, nspace, kw))

        mnames = tuple(base.__name__.lower() for base in mixins)
        nspace['_mixins'] = property(lambda self: (getattr(self, i) for i in mnames))

        dummy = lambda *_1, **_2: tuple()

        def _callmixins(self, name, *args, **kwa):
            for mixin in getattr(self, '_mixins'):
                getattr(mixin, name, dummy)(*args, **kwa)
        nspace['_callmixins'] = _callmixins

        def _yieldovermixins(self, name, *args, **kwa):
            for mixin in getattr(self, '_mixins'):
                yield from getattr(mixin, name, dummy)(*args, **kwa)
        nspace['_yieldovermixins'] = _yieldovermixins

        return type(clsname, bases, nspace)

    @classmethod
    def __addaccesses(mcs, mixins, nspace, kwa):
        match   = re.compile(kwa.get('match', r'^[a-z][a-zA-Z0-9]+$')).match
        members = dict() # type: ignore
        for base in mixins:
            for name, fcn in getmembers(base):
                if match(name) is None or name in nspace:
                    continue
                members.setdefault(name, []).append((base, fcn))

        for name, fcns in members.items():
            if len(set(j for _, j in fcns)) > 1:
                if not kwa.get('selectfirst', False):
                    raise NotImplementedError("Multiple funcs: "+str(fcns))

            base, fcn = fcns[0]
            if _ismeth(fcn) or (_isfunc(fcn) and not ismethod(fcn)):
                yield (name, mcs.__createstatic(fcn))
            elif _isfunc(fcn):
                yield (name, mcs.__createmethod(base, fcn))
            elif isinstance(fcn, Enum):
                yield (name, fcn)
            elif isinstance(fcn, property):
                yield (name, mcs.__createprop(base, fcn))

    @staticmethod
    def __createstatic(fcn):
        @wraps(fcn)
        def _wrap(*args, **kwa):
            return fcn(*args, **kwa)
        return staticmethod(_wrap)

    @staticmethod
    def __createmethod(base, fcn, ):
        cname = base.__name__.lower()
        @wraps(fcn)
        def _wrap(self, *args, **kwa):
            return fcn(getattr(self, cname), *args, **kwa)
        return _wrap

    @staticmethod
    def __createprop(base, prop):
        fget = (None if prop.fget is None
                else lambda self: prop.fget(self.getMixin(base)))
        fset = (None if prop.fset is None
                else lambda self, val: prop.fset(self.getMixin(base), val))
        fdel = (None if prop.fdel is None
                else lambda self: prop.fdel(self.getMixin(base)))

        return property(fget, fset, fdel, prop.__doc__)

def startfile(filepath:str):
    u"launches default application for given file"
    LOGS.info("Launching %s", filepath)
    if sys.platform.startswith('darwin'):
        subprocess.Popen(('open', filepath))
    elif os.name == 'nt':
        old      = os.path.abspath(os.path.curdir)
        filepath = os.path.abspath(filepath)
        os.chdir(os.path.dirname(filepath))
        # pylint: disable=no-member
        try:
            os.startfile(os.path.split(filepath)[-1]) # type: ignore
        except OSError as exc:
            if 'Application not found' not in str(exc):
                raise
        finally:
            os.chdir(old)
    elif os.name == 'posix':
        subprocess.Popen(('xdg-open', filepath),
                         stdout = subprocess.DEVNULL,
                         stderr = subprocess.DEVNULL)

def parseints(new:str) -> Set[int]:
    "returns a set of ints"
    vals: Set[int] = set()
    for i in re.split('[;,]', new):
        for k in '→', '->', 'to', ':':
            if k in i:
                j = i.split(k)
                try:
                    rng = range(int(j[0]), int(j[1])+1)
                except ValueError:
                    continue
                vals.update(rng)
                break
        else:
            try:
                vals.add(int(i))
            except ValueError:
                continue
    return vals

def intlistsummary(beads: Sequence[int], ordered = True, maxi = None) -> str:
    """
    return a string with values in *beads*.

    Sequential values are removed and replaced with a *→*.
    Thus: `[1, 2, 3, 4,  7,8, 10]` becomes `"1 → 4, 7, 8, 10"`.
    """
    beads = list(beads)
    if len(beads) == 0:
        return ""

    short = '...' if maxi and len(beads) > maxi else ''
    if short:
        beads = beads[:maxi]

    if ordered:
        beads = np.sort(beads)

        txt   = ""
        last  = 0
        i     = 1
        while i < len(beads)-1:
            if beads[i] + 1 < beads[i+1]:
                txt    += f", {beads[last]}{', ' if last == i-1 else ' → '}{beads[i]}"
                last, i = i+1, i+2
            else:
                i      += 1

        if last == len(beads)-1:
            txt += ", "+str(beads[last])
        else:
            txt += f", {beads[last]}{', ' if last == len(beads)-2 else ' → '}{beads[-1]}"
        return txt[2]+short
    return ', '.join(str(i) for i in beads)+short

def leastcommonkeys(info, tail = ', ...') -> Dict[str, str]:
    "return simpler names for a list of track files"
    if not isinstance(info, dict):
        info = {i: i for i in info}
    if len(info) == 1:
        return info

    tails  = {i for i, j in info.items() if j.endswith(tail)}
    dflt   = {i: (j[:-len(tail)] if j.endswith(tail) else j) for i, j in info.items()}
    keys   = {i: j.split('_')                                for i, j in dflt.items()}
    common = None
    for i in keys.values():
        common = set(i) if common is None else set(i) & cast(set, common)

    if common:
        keys = {i:'_'.join(k for k in j if k not in common) for i, j in keys.items()}
    else:
        keys = {i:'_'.join(k for k in j) for i, j in keys.items()}

    empties = sum(1 for i in keys.values() if i == '')
    if empties == 1:
        keys[next(i for i, j in keys.items() if j == '')] = 'ref'
    elif empties > 1:
        keys.update({i: dflt[i] for i, j in keys.items() if j == ''})
    return {i: j+(tail if i in tails else '') for i, j in keys.items()}
