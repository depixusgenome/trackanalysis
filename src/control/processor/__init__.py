#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
# General
Processors implement tasks.

The idea is to have different processors depending on the needs: gui or batch.
For example, the former could include caching results, something not needed by
the latter.

Processors' cache are managed in the *cache* module.

## Lazy evaluations

The evaluations are done in lazily. Processors provided methods for updating data
frames which are only applied to those data items (beads, cycles, ...) later
requested by the user.

This has 2 main consequences:

    1. The processor must provide a *transformation method* which acts on a
    dataframe, either updating it or creating a new one. **Root** tasks are different
    in that they should provide an argument-less generator for creating the first
    dataframes.

    2. The processor must use a copy of the task as in its transformation method.
    To make sure of this, closures are tested and any containing objects of type
    *Task* or *Processor* are refused. One may use dictionnaries created through
    *Processor.config()* or pickled tasks to pass on the task configuration to
    the transformation method.

## Multiprocessing:

It is possible to parallelize algorithms. For this, one must provide the processor
with an instance method *canpool* returning *True*. The `control.processor.runner.Runner`
must also be provided with a *ProcessPoolExecutor* in the *Runner.pool* attribute.
It is then up to the user although the following functions are provided in
`control.processor.runner`:

    1. *pooledinput*: get the input, computed in parallel should any previous task
    or its processor return *True* when *isslow* is called.
    2. *poolchunk*: divides keys in equal chunks between processes.
    3. *pooldump*: needed to serialize a list of processors (`Cache` objet) requested
    by *pooledinput*

It's possible to have multiple multiprocessed processors one after the other. One
should be careful to set "*canpool() == True* so that *pooledinput* calls on them
only once per dataframe.

# Examples:

## Affecting one bead at a time:

Here, the bead values are multiplied by a factor. This is done on the fly
when bead data is requested: the data frame stores a action which is called with
a *(bead key, bead data)* pair and must return the same or another such pair.

    >>> from utils              import initargs
    >>> from model.task         import Task, Level
    >>> from processor          import Processor
    >>> from processor.runner   import Runner

    >>> class MyFavoriteTask(Task):
    >>>     "Class containing attributes only: a c-structure"
    >>>     level   = Level.bead
    >>>     factor  = 2.
    >>>     @initargs('attr')
    >>>     def __init__(self, **_):
    >>>         super().__init__(**_)

    >>> class MyFavoriteProcessor(Processor):
    >>>     "The processor knows its task by its name"
    >>>     def run(args:Runner):
    >>>         assert isinstance(self.task, MyFavoriteTask)
    >>>         assert tuple(self.config()) == tuple(self.task.__dict__.items())
    >>>         cnf = self.config()
    >>>         # We then provide a function that acts on a data frame:
    >>>         #   1. It must return the updated frame or a new frame.
    >>>         #   2. It uses a copy of the task's dict because evaluations are
    >>>         #   done lazily and we don't want later changes to impact
    >>>         #   the current evaluation
    >>>         def _action(info):
    >>>             i[1] *= cnf['factor']
    >>>             return i # don'f forget to return a (key, value) pair
    >>>         args.apply(lambda frame: frame.withaction(_action))

## Running computations on all beads on first call:

It can be useful or necessary (see cordrift) to compute everything across all
beads once. This can be done as in the following example.

The call to *withdata* changes the parent data frame to a proxy (*TransformedItems*),
which will compute the everything the first time some piece of data is requested.

The call to *new* is required so as to isolate the tranformation from any
previous one.  This is because dataframe *actions* are applied on the fly, thus
*after* the transformation with no regard to the order in which they were
actually requested.

    >>> class MyComplexTask(Task):
    >>>     ...

    >>> class MyComplexProcessor(Processor):
    >>>     "The processor knows its task by its name"
    >>>     def run(args:Runner):
    >>>         cnf = self.config()
    >>>         def _tranform_all(inputdata):
    >>>             data = dict(inputdata) # request all of the parent's data
    >>>             for i in data.values():
    >>>                 i[:] *= cnf['factor']
    >>>             return data
    >>>         # Use *new()* to enforce the order between this tranformation
    >>>         # and previous ones.
    >>>         args.apply(lambda frame: frame.new().withdata(_tranform_all))

## Running multiprocess computations on all beads:

    >>> class MyPooledTask(Task):
    >>>     ...

    >>> from concurrent.futures import ProcessPoolExecutor
    >>> from functools          import partial
    >>> from control.processor  import Cache
    >>> from control.processor.runner  import pooledinput, poolchunk, pooldump
    >>> class MyPooledProcessor(Processor):
    >>>     "The processor knows its task by its name"
    >>>     def canpool(self):
    >>>         return True
    >>>     def run(args:Runner):
    >>>         args.apply(self.apply(**args.poolkwargs(self.task), **self.config()))
    >>>     @classmethod
    >>>     def _factor(val, frame, iproc):
    >>>         'class methods can be picked: this is needed by ProcessPoolExecutor'
    >>>         keys = poolchunk(tuple(frame.keys()), 4, iproc)
    >>>         return {i: frame[i]*val for i in keys}
    >>>     @classmethod
    >>>     def apply(_*, pool:ProcessPoolExecutor = None, prev:Cache = None, **cnf):
    >>>         assert len(_) == 0
    >>>         if pool is None:
    >>>             raise NotImplementedError()
    >>>         def _tranform_all(frame):
    >>>             data = pooledinput(pool, pooldump(prev), frame)
    >>>             assert isinstance(data, dict)
    >>>             results = dict()
    >>>             fcn     = partial(cls._factor, cnf['factor'], data)
    >>>             for part in pool.map(fcn, range(4)):
    >>>                 results.update(part)
    >>>             return results
    >>>         return lambda frame: frame.new().withdata(_tranform_all)


## Root Task Example:

    >>> from model.task import RootTask
    >>> class MyRootTask(RootTask):
    >>>     ...

    >>> from numpy.random import rand
    >>> class MyRootProcessor(Processor):
    >>>     "The processor knows its task by its name"
    >>>     def run(args:Runner):
    >>>         def _generator():
    >>>             yield Cycles(data = {(0,0): rand(100) })
    >>>         args.apply(_generator)
"""
from .base      import Processor, processors
from .cache     import Cache
from .runner    import Runner, run
from .track     import TrackReaderProcessor, CycleCreatorProcessor, DataSelectionProcessor
