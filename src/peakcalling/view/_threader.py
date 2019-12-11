#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
In charge of thread safety & deciding whether to reset or update the plots
"""
from   abc                     import abstractmethod, ABC
from   copy                    import copy
from   itertools               import repeat, chain
from   functools               import partial, wraps
from   threading               import Lock
from   typing                  import (
    TypeVar, Generic, Dict, Tuple, Optional, Iterator, Any, Set, Union, ClassVar,
    List, Callable
)
import numpy   as np
import pandas  as pd

from   view.plots.ploterror    import PlotError
from   taskcontrol.taskcontrol import ProcessorController
from   taskmodel.application   import setupio
from   taskmodel.dataframe     import DataFrameTask
from   ..model                 import Processors, BasePlotConfig, STORE

Parent   = TypeVar("Parent")
Model    = TypeVar("Model")
PlotType = TypeVar("PlotType", bound = 'BasePlotter')


class _PlotDescr:
    _name: str

    def __set_name__(self, _, name: str):
        self._name = name

    def __get__(self, inst, tpe):
        return self if inst is None else getattr(inst.parent, self._name)

    def __set__(self, inst, val):
        setattr(inst.parent, self._name, val)

class BasePlotter(Generic[Parent]):
    "the class in charge of settng up the plots"
    _IDS:   ClassVar[List[str]]      = ['trackid', 'bead']

    def __init__(self, mdl: Parent, processors: Processors):
        self.parent:   Parent               = mdl
        self._procs:   Processors           = processors

    @staticmethod
    def ishairpin(processors: Processors) -> bool:
        "has FitToHairpinTask in the processors"
        return any(
            hasattr(j, 'sequences') for i in processors.values() for j in i.model
        )

    @staticmethod
    def selectbest(hpin: Set[str], orientation: Set[str], info: pd.DataFrame) -> pd.DataFrame:
        "select the best hairpin for a given bead"
        info = info.nsmallest(1, "cost")
        if len(hpin) >= 1 and info.hpin.values[0] in hpin:
            return info.iloc[:0]

        for i in orientation:
            info = info[info['orientation'] != i]
        return info

    @staticmethod
    def resetstatus(dist: int, info: pd.DataFrame) -> pd.DataFrame:
        """resets the status acording to the distance provided"""
        tpos = info.status.isin(['truepos', 'falseneg'])
        info.loc[info.status == 'truepos',              'status']  = 'falsepos'
        info.loc[tpos & (np.abs(info.distance) < dist), 'status']  = 'truepos'
        info.loc[~tpos,                                 'closest'] = np.NaN
        return info

    def computations(  # pylint: disable=too-many-locals
            self,
            attr: str,
            model,
            tpe: Union[type, Tuple[type, ...]] = pd.DataFrame,
            reqlen: bool = True,
            **kwa: Callable[[Any], Any]
    ) -> Iterator[Tuple[ProcessorController, Any]]:
        "iterates over items in the processors"
        if hasattr(self, attr) and getattr(self, attr).shape[0]:
            cur = set(getattr(self, attr).set_index(self._IDS).index.unique())
        else:
            cur = set()

        tracktag = getattr(model.display, 'tracktag', None)
        roots    = [id(i) for i in model.tasks.roots]
        for proc in self._procs.values():
            iproc: int             = id(proc.model[0])
            cache: Optional[STORE] = proc.data.getcache(DataFrameTask)()
            if not cache or (len(self._procs) > 1 and model.display.masked(root = proc)):
                continue

            cache = dict(cache)  # a little more thread-safe
            for _, ibead in set(zip(repeat(iproc), cache)) - cur:
                info = cache[ibead]
                if (
                        not isinstance(info, tpe)
                        or model.display.masked(root = proc, bead = ibead)
                        or (reqlen and isinstance(info, pd.DataFrame) and not info.shape[0])
                ):
                    continue

                if isinstance(info, pd.DataFrame):
                    info = model.display.filter(info)
                    if reqlen and not info.shape[0]:
                        continue

                info = yield (proc, info)
                if info is not None:
                    info['track']    = f'{roots.index(id(proc.model[0]))}-' + info['track']
                    info['trackid']  = iproc
                    info['bead']     = ibead
                    if tracktag is not None:
                        info['tracktag'] = tracktag.get(proc.model[0], 'none')
                    for i, j in kwa.items():
                        if i in info:
                            info[i] = info[i].apply(j)

                yield info

    @staticmethod
    def cache(proc) -> Optional[STORE]:
        "return the dataframe cache"
        return proc.data.getcache(DataFrameTask)()

    def reset(self, cache):
        "resets the data"
        err = getattr(self.parent, '_errors', None)
        itr = (self._reset if self._isdefault() else self._update)()

        def _display(first, *_):
            for i, j in itr if first is None else chain(first, itr):
                if i is None:
                    continue
                if isinstance(i, Exception) and err is not None:
                    err.reset(cache, i, False)
                elif isinstance(j, dict):
                    cache[i].update(j)
                else:
                    assert i not in cache
                    cache[i] = j

            for widget in getattr(self.parent, '_widgets'):
                widget.reset(self, cache)

        if callable(err):
            err(cache, lambda: [next(itr, (None, None))], _display)
        else:
            _display(cache)

    @staticmethod
    def getdata() -> Dict[str, pd.DataFrame]:
        "return the data to export to xlsx"
        return {}

    @staticmethod
    def _from_df(data) -> Dict[str, np.ndarray]:
        return {i: j.values for i, j in data.items()}

    @staticmethod
    def attr():
        "return a descriptor to access the parent"
        return _PlotDescr()

    @abstractmethod
    def _reset(self):
        "resets the data"

    @abstractmethod
    def _update(self):
        "streams the data"

    @abstractmethod
    def _isdefault(self) -> bool:
        "whether the plot should be started anew or updated"
        return False

class PlotThreader(ABC):
    """
    In charge of thread safety & deciding whether to reset or update the plots
    """
    plot: BasePlotter

    def __init__(self, view):
        self.view        = view
        self.idval: int  = -1
        self.lock:  Lock = Lock()

    def reset(self, cache, fcnname: str = 'reset', delplot: bool = True):
        "runs the first reset"
        idval = -2
        with self.lock:
            idval = self.idval
            if hasattr(self, 'plot') and delplot:
                del self.plot
        self._run(idval, fcnname, cache)

    def update(self, ctrl, idval, fcnname = 'reset', **_):
        "calls an update"
        with self.lock:
            if self.idval != idval and hasattr(self, 'plot'):
                del self.plot
            self.idval = idval

            self.view.reset(ctrl, fcn = partial(self._run, idval, fcnname))

    def renew(self, ctrl, fcnname: str = 'reset', delplot: bool = True, **_):
        "rebuilds from nothing"
        with self.lock:
            if hasattr(self, 'plot') and delplot:
                del self.plot
            self.view.reset(ctrl, fcn = partial(self._run, self.idval, fcnname))

    def _run(self, idval: int, fcnname: str, cache: dict):
        "runs the display"
        if self.idval == idval:
            plot = None
            cpy  = None

            with self.lock:
                plot = getattr(self, 'plot', None)
                if self.idval == idval and plot is None:
                    self.plot = plot = (
                        self.view.createplot() if hasattr(self.view, 'createplot') else
                        self.createplot()
                    )

                cpy = copy(plot)

            if self.idval == idval:
                try:
                    getattr(cpy, fcnname)(cache)
                except Exception:  # pylint: disable=broad-except
                    with self.lock:
                        if hasattr(self, 'plot'):
                            del self.plot
                    raise
                else:
                    with self.lock:
                        plot.__dict__.update(cpy.__dict__)

                    if self.idval != idval:
                        cache.clear()

    def createplot(self) -> BasePlotter:
        "create the righ BasePlotter"
        raise NotImplementedError()

    @classmethod
    def setup(cls, other):
        "sets-up the threader on this class"
        def __init__(self, *args, _old_ = other.__init__, **kwa):
            _old_(self, *args, **kwa)
            setattr(self, '_threader', cls(self))

        def _reset(self, _, cache):
            "resets the plot"
            getattr(self, '_threader').reset(cache)

        def _addtodoc(self, ctrl, doc, _old_ = getattr(other, '_addtodoc')):
            outp = _old_(self, ctrl, doc)
            setattr(self, '_errors', PlotError(getattr(self, '_fig')))
            return outp

        def observe(self, ctrl, _old_ = getattr(other, 'observe', None)):
            """observe the controller"""
            if callable(_old_):
                _old_(self, ctrl)

            model    = getattr(self, '_model')
            model.observe(ctrl)

            threader = getattr(self, '_threader')

            attrdisp = {'hairpins', 'beads', 'roots', 'orientations', 'ranges'}

            @ctrl.display.observe(model.display)
            @ctrl.display.hashwith(self)
            def _onmask(old, **_):
                if attrdisp.intersection(old):
                    threader.renew(ctrl, delplot = True)

            attrs = {'xinfo', 'yaxis'}
            attrs.update(BasePlotConfig().__dict__)

            @ctrl.theme.observe(model.theme)
            @ctrl.theme.hashwith(self)
            def _onconfig(old, **_):
                if set(old) & attrs:
                    threader.renew(ctrl, delplot = True)

            @ctrl.display.observe(model.tasks.eventjobstop)
            @ctrl.display.hashwith(self)
            def _onstop(**_):
                threader.renew(ctrl, delplot = True, **_)

            @ctrl.display.observe(model.tasks.eventname)
            @ctrl.display.hashwith(self)
            def _onupdate(**_):
                threader.update(ctrl, **_)

        for fcn in (__init__, _reset, _addtodoc, observe):
            name = fcn.__name__
            if hasattr(other, name):
                fcn = wraps(getattr(other, name))(fcn)
            setattr(other, name, fcn)

        other.ismain = staticmethod(ismain)
        return other


def ismain(ctrl):
    "Set-up things if this view is the main one"
    setupio(
        ctrl,
        (
            'datacleaning', 'extremumalignment', 'clipping',
            'eventdetection', 'peakselector', 'singlestrand',
            'baselinepeakfilter'
        )
    )
