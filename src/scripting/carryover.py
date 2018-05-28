#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
defines rules of carry over
"""
from collections import namedtuple
from functools   import reduce
from glob        import glob
from os.path     import getmtime
from typing      import List
from holoviews   import Overlay,Curve

import numpy     as np
import pandas    as pd
import regex

from sequences import Translator, overlap
from utils     import initdefaults

REVERSE = Translator().reversecomplement

ChronoItem = namedtuple("ChronoItem",["time","key"])

class CarryOver:
    """
    Defines carry over rules
    compares row of a dataframe and checks if any consecutive row may
    be the consequence of a carry over
    * different peaks whose oligo may overlap are discarded
    * A peak carried from previous experiments should show fewer events
        than the experiment it is originating from
    """
    delta      = 0.003 # in microns
    minoverlap = 2
    @initdefaults(frozenset(locals()))
    def __init__(self,**_)->None:
        pass

    def find(self,data:pd.DataFrame):
        """
        args : dataframe
        groups peaks which could be crosscontaminations.
        "modification" and "peakposition" are used to filter out
        non consecutive experiments or peaks too far from one another
        """
        duplicates = ["track","eventcount","peakposition","modification"]
        df1 = data.drop_duplicates(subset=duplicates).assign(kept=True).copy()
        df1.sort_values(by=["peakposition"],inplace=True)

        mtimes = sorted(set(df1["modification"]))
        pairs: List = []
        for time1,time2 in zip(mtimes[:-1],mtimes[1:]):
            subdf1 = df1[(df1["modification"]==time1)|(df1["modification"]==time2)]
            pairs+=[(subdf1.iloc[i],subdf1.iloc[i+1]) for i in range(subdf1.shape[0]-1)
                    if subdf1.iloc[i+1]["peakposition"]-subdf1.iloc[i]["peakposition"]<self.delta
                    and subdf1.iloc[i+1]["modification"]!=subdf1.iloc[i]["modification"]]

        return filter(self.applyrules,pairs)

    @staticmethod
    def rulelastanalysed(_,second:pd.Series)->bool:
        "It can be an observed carry over iff the latest experiment is kept"
        return second["kept"]

    @staticmethod
    def rulenooverlap(first:pd.Series,second:pd.Series,minoverlap=None)->bool:
        "False if oligos do overlap, True otherwise"
        name1,name2=first["track"],second["track"]
        movl = min(len(name1),len(name2))-1 if minoverlap is None else minoverlap
        return not overlap(name1,name2,minoverlap=movl) and\
            not overlap(REVERSE(name1),REVERSE(name2),minoverlap=movl)

    @staticmethod
    def rulefewerevents(first:pd.Series,second:pd.Series)->bool:
        "True if there is fewer events in the latter experiment"
        return first["eventcount"]>second["eventcount"]

    def applyrules(self,pair) -> bool:
        """
        apply each rule in turn
        A rule is a method returns False if the pair of rows in data
        can be a carry over residue, True otherwise
        """
        first,second=pair
        calls = [getattr(self,func) for func in dir(self) if func.startswith("rule")]
        return reduce(np.logical_and,map(lambda x:x(first,second),calls))

    @staticmethod
    def _toxy(field: pd.Series):
        return field["track"],field["peakposition"]

    def overlaypairs(self,pairs):
        "returns an overlay to display the pairings"
        return Overlay([Curve([self._toxy(f1),self._toxy(f2)])
                        for i,(f1,f2) in enumerate(pairs)])

class DuplicateData:
    '''
    takes a dataframe, duplicates data to mimick the chronology of the experiment
    '''
    def __init__(self,path,match,key:str="track")->None:
        self.match                  = match
        self._pattern               = regex.compile(match) if isinstance(match,str) else match
        self.path                   = path
        self.history:List[ChronoItem] = []
        self.key                    = key

    def __duplicate(self,data:pd.DataFrame)->pd.DataFrame:
        """
        map an item of history (key) to values of in data.
        The history lists the chronological order of experiments
        Each data (matching a key in history) is duplicated by the number of key in history
        the modification date is modified to match the recorded experimental file
        """
        out = data.copy()
        out.assign(kept=True)
        for itm in self.history:
            tmp = data.loc[data[self.key]==itm.key].copy()
            tmp.loc[:,"modification"]= itm.time
            out=out.append(tmp.assign(kept= False))
        return out

    def findhistory(self)->List[ChronoItem]:
        "finds chronological order of experiments using files mtime"
        history = [ChronoItem(self.totimestamp(f),regex.match(self._pattern,f).groups()[0].upper())
                   for f in glob(self.path)
                   if regex.match(self._pattern,f)]
        self.history = sorted(history)
        return self.history

    @staticmethod
    def totimestamp(ifile:str):
        "converts mtime to Timestamps"
        return pd.Timestamp(getmtime(ifile),unit="s")

    def __call__(self,data:pd.DataFrame,history=None):
        "returns a chronological list of experiments conducted for sequencing"
        self.history = self.findhistory() if history is None else history
        return self.__duplicate(data)
