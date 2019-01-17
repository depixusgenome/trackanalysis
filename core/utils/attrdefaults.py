#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"utils"

from    typing         import (TypeVar, Iterable, FrozenSet, Optional, Callable,
                               Sequence, Dict, Any)
import  inspect
from    copy           import deepcopy, copy
from    functools      import wraps
from    enum           import Enum

from   .inspection     import getlocals

NoArgs       = type('NoArgs', (), {})
DefaultValue = NoArgs

def toenum(tpe, val):
    "returns an enum object"
    if not isinstance(tpe, type):
        tpe = type(tpe)
    if not issubclass(tpe, Enum):
        return val
    if isinstance(val, (int, str)):
        elem = next((i for i in tpe if i.value == val), None)
        if elem is None and isinstance(val, str):
            elem = getattr(tpe, val, None)
        if elem is None:
            elem = tpe(val)
        return elem
    if isinstance(val, tpe):
        return val
    if val is not None:
        raise TypeError('"level" attribute has incorrect type')
    return None

class ChangeFields:
    "Context within which given fields are momentarily changed"
    def __init__(self, obj, __items__ = None, **items):
        self.obj = obj
        if __items__ is not None:
            items.update(__items__)
        self.items                = items
        self.olds: Dict[str, Any] = dict()

    def __enter__(self):
        for name, kwdef in self.items.items():
            self.olds[name] = old = getattr(self.obj, name)

            kwdef = toenum(old, kwdef)

            setattr(self.obj, name, kwdef)
        return self.olds

    def __exit__(self, *_):
        for i, j in self.olds.items():
            setattr(self.obj, i , j)

def changefields(obj, __items__ = None, **items):
    "Context within which given fields are momentarily changed"
    return ChangeFields(obj, __items__, **items)

def kwargsdefaults(*items, asinit = True):
    """
    Keyword arguments are used for changing an object's fields before running
    the method.

    Using *asinit* means the same attributes as for __init__ will be allowed.
    This is only valid if initdefaults decorates the __init__
    """
    def _fields(vals):
        assert len(vals) and all(isinstance(i, str) for i in vals)
        accepted = frozenset(vals)
        return lambda _: accepted

    if len(items) == 1 and isinstance(items[0], Iterable) and not isinstance(items[0], str):
        items = items[0] # type: ignore

    if len(items):
        items = tuple(i for i in items if i[0].upper() != i[0])

    call = len(items) == 1 and callable(items[0])
    if call:
        if not asinit:
            fields = fieldnames
        else:
            pot    = getattr(getlocals(1).get('__init__', None), 'KEYS', None)
            fields = fieldnames if pot is None else _fields(pot)
    else:
        fields = fieldnames if not len(items)            else _fields(items)

    def _wrapper(fcn):
        @wraps(fcn)
        def _wrap(self, *args, **kwargs):
            if len(kwargs):
                tochange = {i: kwargs.pop(i) for i in fields(self) & frozenset(kwargs)}
                if len(tochange):
                    with changefields(self, tochange):
                        return fcn(self, *args, **kwargs)

            return fcn(self, *args, **kwargs)
        return _wrap

    return _wrapper(items[0]) if call else _wrapper

def setdefault(self, name, kwargs, roots = ('',), # pylint: disable=too-many-arguments
               cpy = None, deepcpy = None, fieldname = None):
    """
    Uses the class attribute to initialize the object's fields if no keyword
    arguments were provided.
    """
    if fieldname is None:
        fieldname = name

    clsdef = getattr(type(self), fieldname)
    if isinstance(clsdef, property):
        clsdef = getattr(self, fieldname)

    for root in roots:
        kwdef = kwargs.get(root+name, NoArgs)

        if kwdef is NoArgs:
            continue

        setattr(self, fieldname, toenum(clsdef, kwdef))
        break
    else:
        if deepcpy is not None:
            setattr(self, fieldname, deepcopy(getattr(cpy, fieldname)))
        elif isinstance(cpy, dict):
            setattr(self, fieldname, cpy[fieldname])
        elif cpy is not None:
            setattr(self, fieldname, getattr(cpy, fieldname))
        else:
            setattr(self, fieldname, deepcopy(clsdef))

class _Updater:
    __slots__ = ('roots', 'mandatory', 'update', 'call', 'attrs', 'ignore')
    def __init__(self,
                 attrs:Sequence[str],
                 roots:Sequence[str],
                 mandatory: bool,
                 kwa:Dict[str,str]) -> None:
        self.roots     = roots
        self.mandatory = mandatory
        kwa            = {i: (j.lower() if isinstance(j, str) else j)
                          for i, j in kwa.items()}
        self.update    = tuple(i for i in attrs if kwa.get(i, '') == 'update') # type: ignore
        self.call      = tuple((i, j) for i, j in kwa.items() if callable(j)) # type: ignore
        self.ignore    = tuple(i for i in attrs if kwa.get(i, '') == 'ignore')
        self.attrs     = tuple((i, i) for i in attrs if kwa.get(i, '') != 'ignore')
        self.attrs    += tuple((i, j+i if j == '_' else j) for i, j in kwa.items()
                               if isinstance(j, str) and j not in ('update', 'ignore'))
        assert len(set(i for i, _ in self.call)  & set(self.attrs) ) == 0

    def __call__(self, obj, kwargs, cpy = None, deepcpy = None):
        if len(cpy) > 1:
            raise TypeError("__init__ takes at most a single positional"
                            +" argument as a copy constructor")
        else:
            cpy = cpy[0] if len(cpy) == 1 else None

        for name, field in self.attrs:
            if self.mandatory and cpy is None and deepcpy is None and name not in kwargs:
                raise KeyError("Missing keyword '%s' in __init__" % name)
            else:
                setdefault(obj, name, kwargs, self.roots, cpy, deepcpy, field)

        for name in self.update:
            update(getattr(obj, name), **kwargs)

        for name, fcn in self.call:
            if name in kwargs:
                fcn(obj, kwargs[name])

def initdefaults(*attrs, roots = ('',), mandatory = False, **kwa):
    """
    Creates an *__init__* such that instance fields and their default value are
    defined using class fields. The default values are deepcopied into each instance.

    Exemple:

        >>> class Cls:
        >>>     attr       = [] # the default list will be deepcopied in each instance
        >>>     ignored    = 0  # field will not be initialized
        >>>     _protected = 1  # field will be initialized with a specific keyword
        >>>     @initdefaults(frozenset(locals()),
        >>>                   ignored = 'ignore',
        >>>                   call    = lambda self, value: setattr(self, 'ignored', 2*value),
        >>>                   protect = "_protected")
        >>>     def __init__(self, **kwa):
        >>>         pass

        >>> assert Cls().ignored               == 0
        >>> assert Cls(call = 1).ignored       == 2
        >>> assert Cls()._protected            == 1
        >>> assert Cls(protect = 2)._protected == 2
        >>> assert Cls().attr                  == []
        >>> assert Cls().attr                  is not Cls.attr
        >>> lst = [2]
        >>> assert Cls(attr = lst).attr        is lst # no deep copy of passed values

    By decorating the *__init__* as follows, it's possible to affect passed values

        >>> class Trans:
        >>>     attr1 = 1
        >>>     attr2 = 2
        >>>     @initdefaults(frozenset(locals()))
        >>>     def __init__(self, *kwa:dict, **_) -> None: # _ is needed by pylint
        >>>         kwa[0].pop('attr1', None)
        >>>         if 'attr2' in kwa[0]:
        >>>             kwa[0]['attr2'] *= 2

        >>> assert Trans(attr1 = 100).attr1 == 1
        >>> assert Trans(attr2 = 100).attr2 == 200


    One can update grandchild fields using kwargs:

        >>> class Agg:
        >>>     elem = Cls()
        >>>     @initdefaults(frozenset(locals()), elem = 'update')
        >>>     def __init__(self, **kwa):
        >>>         pass

        >>> assert Agg(attr = [2]).elem.attr == [2]

    """

    fcn     = None
    if len(attrs) == 1 and isinstance(attrs[0], Iterable) and not isinstance(attrs[0], str):
        attrs = attrs[0] # type: ignore

    delayed = next((i for i in attrs if i == '__delayed_init__'), None) is not None
    attrs   = tuple(i for i in attrs if i != '__delayed_init__')

    if len(attrs) == 1 and callable(attrs[0]):
        fcn   = attrs[0]
        attrs = ()

    if len(attrs) == 0:
        attrs = tuple(i for i in getlocals(1).keys())

    assert len(attrs) and all(isinstance(i, str) for i in attrs)
    attrs = tuple(i for i in attrs if i[0].upper() != i[0])

    def _wrapper(fcn):
        sig       = inspect.signature(fcn).parameters
        val       = tuple(sig.values())[1]
        initafter = kwa.pop('initafter', False)
        updater   = _Updater(attrs, roots, mandatory, kwa)
        if val.kind  == val.VAR_KEYWORD and initafter:
            def __init__(self, *args, **kwargs):
                updater(self, kwargs, cpy = args)
                fcn    (self, **kwargs)
                if delayed:
                    self.__delayed_init__(kwargs)

            setattr(__init__, 'IS_GET_STATE', True)

        elif val.kind  == val.VAR_KEYWORD and not initafter:
            def __init__(self, *args, **kwargs):
                fcn    (self, **kwargs)
                updater(self, kwargs, cpy = args)
                if delayed:
                    self.__delayed_init__(kwargs)
            setattr(__init__, 'IS_GET_STATE', True)

        elif initafter:
            def __init__(self, *args, **kwargs):
                updater(self, kwargs)
                fcn    (self, *args, **kwargs)
                if delayed:
                    self.__delayed_init__(*args, **kwargs)

        elif ((val.annotation, val.kind) == (dict, val.VAR_POSITIONAL)
              and (len(sig) == 2 or (len(sig) == 3 and tuple(sig)[2] == '_'))):
            def __init__(self, *args, **kwargs):
                fcn    (self, kwargs)
                updater(self, kwargs, cpy = args)
                if delayed:
                    self.__delayed_init__(kwargs)
            setattr(__init__, 'IS_GET_STATE', True)

        else:
            def __init__(self, *args, **kwargs):
                fcn    (self, *args, **kwargs)
                updater(self, kwargs)
                if delayed:
                    self.__delayed_init__(*args, **kwargs)

        setattr(__init__, 'UPDATER', updater)
        setattr(__init__, 'KEYS',    attrs)
        return wraps(fcn)(__init__)

    return _wrapper if fcn is None else _wrapper(fcn)

def addattributes(cls, *_, protected: Dict[str, Any] = None, **kwa):
    "Adds attributes to a class with its `__init__` previously decorated by `@initdefaults`"
    if isinstance(protected, dict):
        for i, j in protected.items():
            setattr(cls, '_'+i, j)
        cls.__init__.UPDATER.attrs  += tuple((i, '_'+i) for i in protected)

    for i, j in kwa.items():
        setattr(cls, i, j)
    cls.__init__.UPDATER.attrs  += tuple((i, i) for i in kwa)

Type = TypeVar('Type')
def fieldnames(obj) -> FrozenSet[str]:
    "Returns attribute and property names of the object"
    dico = frozenset(name
                     for name in getattr(obj, '__dict__', ())
                     if 'a' <= name[0] <= 'z')
    desc = frozenset(name
                     for name, tpe in obj.__class__.__dict__.items()
                     if ('a' <= name[0] <= 'z'
                         and callable(getattr(tpe, '__set__', None))
                         and not getattr(tpe, 'fset', '') is None))
    return dico | desc

def _update(cpy: Optional[Callable[[Type], Type]], obj:Type, always:bool, **attrs) -> Type:
    "Sets field to provided values"
    fields = fieldnames(obj) & frozenset(attrs)
    if cpy is not None and (always or len(fields)):
        obj = cpy(obj)

    if len(fields):
        for name in fields:
            val = attrs[name]
            if val is not NoArgs:
                setattr(obj, name, val)
    return obj

def update(obj:Type, **attrs) -> Type:
    "Sets field to provided values"
    return _update(None, obj, False, **attrs)

def updatecopy(obj:Type, _always_ = False, **attrs) -> Type:
    "Sets field to provided values on a copied object"
    return _update(copy, obj, _always_, **attrs)

def updatedeepcopy(obj:Type, _always_ = False, **attrs) -> Type:
    "Sets field to provided values on a deepcopied object"
    return _update(deepcopy, obj, _always_, **attrs)
