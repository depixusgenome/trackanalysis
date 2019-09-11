#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing                          import Dict, Tuple
import pandas as pd
import numpy  as np
from   taskcontrol.processor.dataframe import DataFrameFactory
from   data                            import Beads
from   ..beadsubtraction               import FixedBeadDetection
from   ._datacleaning                  import (
    DataCleaningTask, DataCleaningException, Partial
)

@DataFrameFactory.adddoc
class CleaningDataFrameFactory(DataFrameFactory[Beads]):
    """
    Transform cleaning info to one or more `pandas.DataFrame`.

    # Options

    ## No options

    Providing with no measures creates one or more dataframes with one row per
    type of cleaning test and cycle. The columns are:

    * *cycle*
    * *testtype*
    * *testvalue*
    * *testtoolow* is true if *testvalue* is too low to pass,
    * *testtoohigh* is true if *testvalue* is too high to pass,


    ## `fixed` option

    One can use:

    ```python
    DataFrameTask(measures = dict(fixed = True))  # or even: dict(fixed = FixedBeadDetection())
    ```

    Then the dataframe created is one for selecting fixed beads. There is one
    row per bead and multiple columns corresponding to the tests for selecting
    fixed beads (see `cleaning.beadsubtraction.FixedBeadDetection.dataframe`).

    ## `status` option

    One can use:

    ```python
    DataFrameTask(measures = dict(fixed = True, status = True))  # or simply: dict(status = True)
    ```

    Then the dataframe is the same as when using the `fixed` option with one
    extra *status* column. The latter contains one dataframe relative to the
    row's bead. That dataframe is the one produced when no options are provided.
    """
    def __init__(self, task, buffers, frame):
        self.__status  = task.measures.get('status', False)
        self.__fixed   = (
            task.measures['fixed']
            if isinstance(task.measures.get('fixed', None), FixedBeadDetection) else
            FixedBeadDetection()
            if task.measures.get('fixed', task.measures.get('status', False)) else
            None
        )
        self.__actions  = frame.actions
        try:
            self.__cleaning = buffers.getcache(DataCleaningTask)()
        except IndexError:
            self.__cleaning = {}
        super().__init__(task, frame)

    @classmethod
    def _proc_apply(cls, task, buffers, frame):
        try:
            frame.actions = [cls(task, buffers, frame).dataframe]
            return frame
        except IndexError:
            pass
        return None

    def dataframe(self, frame, info):
        "creates a dataframe"
        cpy = np.copy(info[1]) if self.__status or self.__fixed else info[1]
        try:
            for i in self.__actions:
                info = i(frame, info)
        except DataCleaningException as exc:
            stats = (cpy, exc.args[0].stats, True)  # pylint: disable=no-member
        else:
            if info[0] in self.__cleaning:
                stats = (cpy, self.__cleaning[info[0]].errors, False)
            else:
                stats = (cpy, (), False)

        return super().dataframe(frame, (info[0], stats))

    # pylint: disable=arguments-differ
    @staticmethod
    def dictionary(parts: Tuple[Partial,...]) -> Dict[str, np.ndarray]:
        "error dictionary"
        sizes = [len(i.values) for i in parts]
        if not any(sizes):
            return dict.fromkeys(
                ('cycle', 'testtype', 'testvalue', 'testtoolow', 'testtoohigh'), []
            )

        def _too(vals, cycs):
            out       = np.zeros(len(vals.values), dtype = 'bool')
            out[cycs] = True
            return out

        return {
            'cycle':       np.concatenate([np.arange(i, dtype = 'i4') for i in sizes]),
            'testtype':    np.concatenate([np.full(len(i.values), i.name) for i in parts]),
            'testvalue':   np.concatenate([i.values for i in parts]),
            'testtoolow':  np.concatenate([_too(i, i.min) for i in parts]),
            'testtoohigh': np.concatenate([_too(i, i.max) for i in parts])
        }

    def _run(self, frame, bead, info) -> Dict[str, np.ndarray]:  # pylint: disable=arguments-differ
        if not self.__fixed and not self.__status:
            return dict(
                self.dictionary(info[1]),
                bad = np.full(sum(len(i.values) for i in info[1]), info[2], dtype = 'bool')
            )

        dframe = self.__fixed.dataframe(frame.new(data = {bead: info[0]}))
        out    = dict(
            {
                ('fixed' if i == 'good' else i): dframe[i].values
                for i in dframe.columns if i not in ('track', 'bead')
            },
            bad = info[2] and not dframe.good.values[0],
        )
        if self.__status:
            out['status']    = np.array([None], dtype = 'O')
            out['status'][0] = pd.DataFrame(self.dictionary(info[1]))
        return out
