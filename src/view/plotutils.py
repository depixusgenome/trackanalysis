#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for dealing with the JS side of the view"
from    typing       import (Tuple, Optional, # pylint: disable =unused-import
                             Iterator, List, Union, Any)
from    collections  import OrderedDict
from    contextlib   import contextmanager
from    itertools    import product
from    functools    import wraps
from    pathlib      import Path
import  inspect

import  numpy        as     np

import  bokeh.palettes
import  bokeh.core.properties   as     props
from    bokeh.models            import (Row, CustomJS, Range1d, Model, HoverTool,
                                        RadioButtonGroup, Paragraph)
from    bokeh.plotting.figure   import Figure

from    sequences               import read as _readsequences

from    model.task              import RootTask, Task
from    data.track              import Track
from    utils                   import CachedIO, NoArgs, updatecopy, updatedeepcopy
from    control                 import Controller
from    control.globalscontrol  import GlobalsAccess
from    .base                   import BokehView, Action

def checksizes(fcn):
    "Checks that the ColumnDataSource have same sizes"
    @wraps(fcn)
    def _wrap(*args, **kwa):
        res  = fcn(*args, **kwa)
        if len(res) == 0:
            return res
        size = len(next(iter(res.values())))
        assert all(size == len(i) for i in res.values())
        return res
    return _wrap

_CACHE = CachedIO(lambda path: OrderedDict(_readsequences(path)), size = 1)
def readsequence(path):
    "Reads / caches DNA sequences"
    if path is None or not Path(path).exists():
        return dict()
    try:
        return _CACHE(path)
    except: # pylint: disable=bare-except
        return dict()

class DpxKeyedRow(Row):
    "define div with tabIndex"
    fig                = props.Instance(Figure)
    toolbar            = props.Instance(Model)
    keys               = props.Dict(props.String, props.String, help = 'keys and their action')
    zoomrate           = props.Float()
    panrate            = props.Float()
    __implementation__ = 'keyedrow.coffee'
    def __init__(self, plotter, fig, **kwa):
        vals = ('.'.join(i) for i in product(('pan', 'zoom'), ('x', 'y'), ('low', 'high')))
        cnf   = plotter.config.keypress

        keys  = dict((cnf[key].get(), key) for key in vals)
        keys[cnf.reset.get()] = 'reset'
        keys.update({cnf[tool].activate.get(): tool for tool in ('pan', 'zoom')})

        kwa.setdefault('sizing_mode', 'stretch_both')
        children = kwa.pop('children', [fig])
        super().__init__(children = children,
                         fig      = fig,
                         keys     = keys,
                         zoomrate = cnf.zoom.rate.get(),
                         panrate  = cnf.pan.rate.get(),
                         **kwa)

class DpxHoverTool(HoverTool):
    "sorts indices before displaying tooltips"
    maxcount           = props.Int(5)
    __implementation__ = """
    import * as p  from "core/properties"
    import {HoverTool, HoverToolView} from "models/tools/inspectors/hover_tool"

    export class DpxHoverToolView extends HoverToolView
        _update: (indices, tool, renderer, ds, {geometry}) ->
            inds = indices['1d'].indices
            if inds?.length > 1
                inds.sort((a,b) => a - b)
                if inds.length > @model.maxcount
                    ind = Math.floor((inds.length - @model.maxcount)*0.5)
                    indices['1d'].indices = inds.slice(ind, ind+@model.maxcount)
            super(indices, tool, renderer, ds, {geometry})

    export class DpxHoverTool extends HoverTool
        default_view: DpxHoverToolView
        @define { maxcount: [ p.Int, 5] }
    """

class PlotAttrs:
    "Plot Attributes for one variable"
    def __init__(self,
                 color                  = 'blue',
                 glyph                  = 'line',
                 size                   = 1,
                 palette: Optional[str] = None,
                 **kwa) -> None:
        self.color   = color
        self.glyph   = glyph
        self.size    = size
        self.palette = palette
        self.__dict__.update(kwa)

    def iterpalette(self, count, *tochange, indexes = None) -> Iterator['PlotAttrs']:
        "yields PlotAttrs with colors along the palette provided"
        info    = dict(self.__dict__)
        palette = getattr(bokeh.palettes, self.palette, None)

        if palette is None:
            for _ in range(count):
                yield PlotAttrs(**info)
            return

        colors = palette(count)
        if indexes is not None:
            colors = [colors[i] for i in indexes]

        if len(tochange) == 0:
            tochange = ('color',)

        for color in colors:
            info.update((name, color) for name in tochange)
            yield PlotAttrs(**info)

    def listpalette(self, count, indexes = None) -> List[str]:
        "yields PlotAttrs with colors along the palette provided"
        palette = getattr(bokeh.palettes, self.palette, None)
        if palette is None:
            return [self.color]*count

        colors = palette(count)
        if indexes is not None:
            return [colors[i] for i in indexes]
        else:
            return colors


    def addto(self, fig, **kwa):
        "adds itself to plot: defines color, size and glyph to use"
        args  = dict(self.__dict__)
        args.pop('glyph')
        args.pop('palette')
        args.update(kwa)

        if self.glyph == 'circle' and 'radius' in args:
            args.pop('size')

        if self.glyph in ('line', 'quad'):
            args['line_width'] = args.pop('size')

        return getattr(fig, self.glyph)(**args)

class PlotCreator(GlobalsAccess):
    "Base plotter class"
    def __init__(self, ctrl:Controller) -> None:
        "sets up this plotter's info"
        ctrl.addGlobalMap(self.key())
        ctrl.addGlobalMap(self.key('current'))
        ctrl.addGlobalMap("css.plot",
                          ylabel    = u'Z',
                          xtoplabel = u'Time',
                          xlabel    = u'Frames')
        ctrl.addGlobalMap(self.key('css'))

        super().__init__(ctrl, self.key())
        self._ctrl  = ctrl
        self._ready = False

    def action(self, fcn):
        u"decorator which starts a user action unless _ready is set to false"
        if tuple(inspect.signature(fcn).parameters) == ('attr', 'old', 'new'):
            @wraps(fcn)
            def _wrap_cb(attr, old, new):
                if self._ready:
                    with Action(self._ctrl):
                        fcn(attr, old, new)
            return _wrap_cb
        elif tuple(inspect.signature(fcn).parameters)[1:] == ('attr', 'old', 'new'):
            @wraps(fcn)
            def _wrap_cb(self, attr, old, new):
                if self._ready:
                    with Action(self._ctrl):
                        fcn(self, attr, old, new)
            return _wrap_cb
        else:
            @wraps(fcn)
            def _wrap_cb(*args, **kwa):
                if self._ready:
                    with Action(self._ctrl):
                        fcn(*args, **kwa)
            return _wrap_cb

    @contextmanager
    def updating(self):
        "Stops on_change events for a time"
        self._ready = False
        yield self
        self._ready = True

    @staticmethod
    def fixreset(arng):
        "Corrects the reset bug in bokeh"
        assert isinstance(arng, Range1d)
        def _onchangebounds(rng = arng):
            # pylint: disable=protected-access,no-member
            if rng.bounds is not None:
                rng._initial_start = rng.bounds[0]
                rng._initial_end   = rng.bounds[1]

        arng.callback = CustomJS.from_py_func(_onchangebounds)

    @classmethod
    def key(cls, base = 'config'):
        "Returns the key used by the global variables"
        return base+".plot."+cls.__name__[:-len('PlotCreator')].lower()

    def close(self):
        "Removes the controller"
        del self._ctrl

    def create(self, doc):
        "returns the figure"
        raise NotImplementedError("need to create")

    def _figargs(self):
        tools = self.config.tools.get()
        if 'dpxhover' in tools:
            tools = [i if i != 'dpxhover' else DpxHoverTool() for i in tools.split(',')]
        return dict(tools          = tools,
                    toolbar_sticky = False,
                    sizing_mode    = 'stretch_both')

    def newbounds(self, rng, axis, arr) -> dict:
        "Sets the range boundaries"
        over  = self.config.boundary.overshoot.get()

        if isinstance(arr, np.ndarray):
            vmin  = np.nanmin(arr)
            vmax  = np.nanmax(arr)
        else:
            vmin  = min(arr)
            vmax  = max(arr)
        delta = (vmax-vmin)*over*.5
        vmin -= delta
        vmax += delta

        if axis is None:
            curr  = None, None # type: Tuple[Optional[float], Optional[float]]
        else:
            curr  = self.project[axis].get(default = (vmin, vmax))

        attrs = dict(bounds        = (vmin, vmax),
                     start         = vmin if curr[0]  is None else curr[0],
                     end           = vmax if curr[1]  is None else curr[1],
                     range_padding = over*100.)
        if not hasattr(rng, 'range_padding'):
            attrs.pop('range_padding')

        return attrs

    def _addcallbacks(self, fig):
        "adds Range callbacks"
        cnf       = self.project
        def _onchangex_cb(attr, old, new):
            if self._ready:
                cnf.update(x = (fig.x_range.start, fig.x_range.end))
        fig.x_range.on_change('start', _onchangex_cb)
        fig.x_range.on_change('end',   _onchangex_cb)

        def _onchangey_cb(attr, old, new):
            if self._ready:
                cnf.update(y = (fig.y_range.start, fig.y_range.end))

        fig.y_range.on_change('start', _onchangey_cb)
        fig.y_range.on_change('end',   _onchangey_cb)

        cnf.defaults = dict(x = (None, None), y = (None, None))

        def _onobserve(items):
            for i in {'x', 'y'} & frozenset(items):
                vals = items[i].value
                getattr(fig, i+'_range').update(start = vals[0], end = vals[1])

        self.project.observe(('x', 'y'), _onobserve)
        return fig

    def setbounds(self, rng, axis, arr, reinit = True):
        "Sets the range boundaries"
        if reinit and hasattr(rng, 'reinit'):
            rng.update(reinit = not rng.reinit, **self.newbounds(rng, axis, arr))
        else:
            rng.update(**self.newbounds(rng, axis, arr))

    def bounds(self, arr):
        "Returns boundaries for a column"
        if len(arr) == 0:
            return 0., 1.

        vmin  = min(arr)
        vmax  = max(arr)
        delta = (vmax-vmin)*self.config.boundary.overshoot.get()
        vmin -= delta
        vmax += delta
        return vmin, vmax

class PlotModelAccess(GlobalsAccess):
    "Contains all access to model items likely to be set by user actions"
    def __init__(self,
                 ctrl: Union['PlotModelAccess', Controller],
                 key:  Optional[str] = None,
                 **_) -> None:
        super().__init__(ctrl, key)
        self._ctrl = getattr(ctrl, '_ctrl', ctrl)

        super().__init__(ctrl, key)
        for attr in self._cached():
            self.project[attr].setdefault(None)
        self.clearcache()

    @property
    def bead(self) -> Optional[int]:
        "returns the current bead number"
        bead = self.project.bead.get()
        if bead is None:
            track = self.track
            if track is not None:
                return next(iter(track.beadsonly.keys()))
        return bead

    @property
    def roottask(self) -> Optional[RootTask]:
        "returns the current root task"
        return self.project.track.get()

    @property
    def currenttask(self) -> Optional[Task]:
        "returns the current task"
        return self.project.task.get()

    @property
    def track(self) -> Optional[Track]:
        "returns the current track"
        return self._ctrl.track(self.roottask)

    def clearcache(self):
        u"updates the model when a new track is loaded"
        self.project.update({i: dict() for i in self._cached()})

    def checktask(self, root, task):
        "checks wether a task belongs to the model"
        if not any(val.check(task) for val in self.__dict__.values()
                   if isinstance(val, TaskAccess)):
            return False

        return root is self.roottask

    def runbead(self):
        "returns a tuple (dataitem, bead) to be displayed"
        track = self.track
        if track is None:
            return None, None, None

        root  = self.roottask
        for task in tuple(self._ctrl.tasks(root))[::-1]:
            if self.checktask(root, task):
                ibead = self.bead
                beads = next(iter(self._ctrl.run(root, task, copy = True)))
                return track, beads[ibead,...], ibead

        return track, track.cycles[self.bead,...], self.bead

    def observetasks(self, *args, **kwa):
        "observes the provided task"
        def _check(parent = None, task = None, **_):
            return self.checktask(parent, task)
        self._ctrl.observe(*args, argstest = _check, **kwa)

    class _Props:
        @staticmethod
        def configroot(attr):
            "returns a property which links to the config"
            # pylint: disable=protected-access
            def _getter(self):
                return self.configroot[attr].get()

            def _setter(self, val):
                return self.configroot[attr].set(val)

            hmsg  = "link to config's {}".format(attr)
            return property(_getter, _setter, None, hmsg)

        @staticmethod
        def config(attr):
            "returns a property which links to the config"
            def _getter(self):
                return self.config[attr].get()

            def _setter(self, val):
                self.config[attr].set(val)

            hmsg  = "link to config's {}".format(attr)
            return property(_getter, _setter, None, hmsg)

        @staticmethod
        def bead(attr):
            "returns a property which links to the current bead or the config"
            def _getter(self):
                value = self.project[attr].get().get(self.bead, NoArgs)
                if value is not NoArgs:
                    return value
                return self.config[attr].get()

            def _setter(self, val):
                cache = self.project[attr].get()
                if val == self.config[attr].get():
                    cache.pop(self.bead, None)
                else:
                    cache[self.bead] = val
            hmsg     = "link to config's {}".format(attr)
            prop     = property(_getter, _setter, None, hmsg)
            prop.KEY = attr
            return prop

    props = _Props()
    del _Props

    @classmethod
    def _cached(cls):
        pred = lambda x: isinstance(x, property) and hasattr(x, 'KEY')
        yield from (value.KEY for _, value in inspect.getmembers(cls, pred))

class TaskAccess(PlotModelAccess):
    "access to tasks"
    def __init__(self,
                 ctrl       : PlotModelAccess,
                 tasktype   : type,
                 order      : Tuple[type,...],
                 **kwa) -> None:
        super().__init__(ctrl)
        side    = kwa.get('side', 'LEFT')
        attrs   = kwa.get('attrs', {})
        default = tasktype(**attrs)

        self.defaultindex = order.index(type(default)) + (1 if side == 'RIGHT' else 0)
        self.previous     = order[:self.defaultindex]
        self.tasktype     = type(default)
        self.attrs        = attrs

        # pylint: disable=not-callable
        self.configroot.tasks[self.configname].default = default

    @property
    def configname(self) -> str:
        "returns the config name"
        return self.__class__.__name__.lower()[:-len('Access')]

    @property
    def configtask(self) -> Task:
        "returns the config task"
        return self.configroot.tasks[self.configname]

    def remove(self):
        "removes the task"
        task = self.task
        if task is not None:
            self._ctrl.removeTask(self.roottask, task)

            cnf = self.configtask
            cnf.set(updatecopy(cnf.get(), disabled = True))

    def update(self, **kwa):
        "removes the task"
        root = self.roottask
        task = self.task
        cnf  = self.configtask
        if task is None:
            kwa.setdefault('disabled', False)
            item = updatedeepcopy(cnf.get(), **kwa)
            self._ctrl.addTask(root, item, index = self.index)
        else:
            self._ctrl.updateTask(root, task, **kwa)
        cnf.set(updatecopy(cnf.get(), **kwa))

    @property
    def task(self) -> Optional[Task]:
        "returns the task if it exists"
        return next((t for t in self._ctrl.tasks(self.roottask) if self.check(t)), None)

    def check(self, task, parent = NoArgs) -> bool:
        "wether this controller deals with this task"
        if not (isinstance(task, self.tasktype) and self._check(task)):
            return False
        if parent is NoArgs:
            return True
        return parent is self.roottask

    @staticmethod
    def _check(_) -> bool:
        return True

    @staticmethod
    def _default() -> dict:
        return {}

    @property
    def index(self) -> Optional[Task]:
        "returns the index the new task should have"
        tasks = tuple(self._ctrl.tasks(self.roottask))
        for i, tsk in enumerate(tasks[1:]):
            if not isinstance(tsk, self.previous):
                return i+1
        return len(tasks)

    def observe(self, *args, **kwa):
        "observes the provided task"
        def _check(parent = None, task = None, **_):
            return self.check(task, parent)
        self._ctrl.observe(*args, argstest = _check, **kwa)

class WidgetCreator(GlobalsAccess):
    "Base class for creating a widget"
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self._model = model
        self._ctrl  = getattr(model, '_ctrl')

class GroupCreator(WidgetCreator):
    "Allows creating group widgets"
    INPUT = RadioButtonGroup
    def __init__(self, model:PlotModelAccess) -> None:
        super().__init__(model)
        self._widget  = None # type: ignore

    def create(self, action):
        "creates the widget"
        name = self.__class__.__name__[:-len('Creator')]
        css  = self.css.title[name.lower()]
        self._widget = self.INPUT(labels = css.labels.get(),
                                  name   = 'Cycles:'+name,
                                  **self._data())
        self._widget.on_click(action(self.onclick_cb))

        if css.get(default = None) is not None:
            return Paragraph(text = css.get()), self._widget
        return self._widget,

    def update(self):
        "updates the widget"
        self._widget.update(**self._data())

    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"
        raise NotImplementedError()

    def _data(self) -> dict:
        raise NotImplementedError()

class TrackPlotCreator(PlotCreator):
    "Base plotter for tracks"
    _MODEL = PlotModelAccess
    def __init__(self, ctrl, *_):
        super().__init__(ctrl, *_)
        self._model = self._MODEL(ctrl, self.key(''))

    def create(self, doc) -> DpxKeyedRow:
        "returns the figure"
        return self._create(doc, *self._gettrack())

    def update(self, items:dict):
        "Updates the data"
        if not self._needsupdate(items):
            return

        with self.updating():
            self._update(items, *self._gettrack())

    def _create(self, doc, *args) -> DpxKeyedRow:
        raise NotImplementedError()

    @staticmethod
    def _needsupdate(items):
        return 'track' in items or 'bead' in items

    def _update(self, items, *args):
        raise NotImplementedError()

    def _gettrack(self) -> Tuple[Track, int]:
        return self._model.track, self._model.bead

class TrackPlotView(BokehView):
    "Track plot view"
    PLOTTER = None # type: Optional[type]
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._plotter = self.PLOTTER(self._ctrl) # pylint: disable=not-callable
        self._ctrl.getGlobal("current").bead.default = None

    def close(self):
        "remove controller"
        super().close()
        self._plotter.close()
        self._plotter = None

    def _onUpdateCurrent(self, items:dict):
        self._plotter.update(items) # pylint: disable=no-member

    def getroots(self, doc):
        "adds items to doc"
        self._ctrl.getGlobal('current').observe(self._onUpdateCurrent)
        return self._plotter.create(doc),
