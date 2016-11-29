#! /usr/bin/env python
# encoding: utf-8
u"Small library for computing ramp characteristics"
import pandas as pd
from numpy import nan, isfinite # type: ignore
from data import Track

class RampModel():
    u''' holds instruction to handle the data'''
    def __init__(self):
        self.scale = 5.0
        self.needsCleaning = False

class RampControler():
    u'''sets up ramp analysis using RampModel for parametrisation'''
    def __init__(self, datf:pd.DataFrame, model:RampModel) -> None:
        self.dataz = datf
        self.model = model
        self.dzdt = None
        self.bcids = None
        self.beads = None
        self.ncycles = None
        self._setup()

    @classmethod
    def fromFile(cls,filename:str,model:RampModel):
        u''' reads RampControler from track file'''
        trks = Track(path = filename)
        datf = pd.DataFrame({k:pd.Series(v) for k, v in dict(trks.cycles).items()})
        return cls(datf, model)

    @classmethod
    def FromTrack(cls,trks:Track, model:RampModel):
        u'''Uses a Track to initialise the RampControler'''
        datf = pd.DataFrame({k:pd.Series(v) for k, v in dict(trks.cycles).items()})
        return cls(datf, model)

    def _setup(self):
        self.dzdt = self.dataz.rename_axis(lambda x:x-1)-self.dataz.rename_axis(lambda x:x+1)
        self.bcids = {k for k in self.dzdt.keys() if isinstance(k[0], int)}
        self.beads = {i[0] for i in self.bcids}
        self.ncycles = max(i[1] for i in self.bcids) +1
        if self.model.needsCleaning:
            self.model.needsCleaning = False
            self.stripBadBeads()

        self.det = detectOutliers(self.dzdt,self.model.scale)


    def zmagClose(self, reverse_time:bool = False):
        u'''estimate value of zmag to close the hairpin'''
        if reverse_time:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.last_valid_index())
        else:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.first_valid_index())

        zmcl = pd.DataFrame(index = self.beads, columns = range(self.ncycles))
        for bcid in self.bcids:
            zmcl.loc[bcid[0], bcid[1]] = self.dataz[("zmag", bcid[1])][ids[bcid]] if isfinite(ids[bcid]) else nan

        return zmcl


    def zmagOpen(self)->pd.DataFrame:
        u''' estimate value of zmag to open the hairpin'''
        ids = self.dzdt[self.dzdt[self.det]>0].apply(lambda x:x.last_valid_index())
        zmop = pd.DataFrame(index = self.beads, columns = range(self.ncycles))
        for bcid in self.bcids:
            zmop.loc[bcid[0], bcid[1]] = self.dataz[("zmag", bcid[1])][ids[bcid]] if isfinite(ids[bcid]) else nan

        return zmop

    def stripBadBeads(self):
        u'''good beads open and close with zmag
        All cycles of a bead  must match the conditions for qualification as good bead.
        This condition may be too harsh for some track files (will improve).
        '''
        good = self.dzdt.apply(lambda x: _isGoodBead(x,scale = self.model.scale))
        todel = {k[0] for k in self.bcids if not good[k]}
        keys = [k for k in self.dataz.keys() if k[0] not in todel] # harsh condition (relax? modify? additional test?) see bead 19 cycle 11 from test ramp file

        self.dataz = self.dataz[keys]
        self.dzdt = self.dzdt[keys]
        self.bcids = {k for k in self.dzdt.keys() if isinstance(k[0], int)}
        self.beads = {i[0] for i in self.bcids}
        self.ncycles = max(i[1] for i in self.bcids) +1
        return



def _isGoodBead(dzdt:pd.Series,scale:int):
    u'''test a single bead over a single cycle'''
    det = detectOutliers(dzdt,scale)
    # at least one opening and closing
    if not (any(dzdt[det]>0) and any(dzdt[det]<0)):
        return False

    # last index of positive detected dzdt
    lposid = dzdt[(dzdt>0)&det].last_valid_index()
    negids = dzdt[(dzdt<0)&det].index

    return not any((negids-lposid)<0)


def detectOutliers(dzdt,scale:int):
    u'''detects opening and closing '''
    # quantile detection
    quant1 = dzdt.quantile(0.25)
    quant3 = dzdt.quantile(0.75)
    max_outlier = quant3+scale*(quant3-quant1)
    min_outlier = quant1-scale*(quant3-quant1)
    return (dzdt>max_outlier)|(dzdt<min_outlier)


def crossHasBead():
    u'''Check whether there is a bead under the cross'''
    # to implement
    return


def fixedBead():
    u''' bead does not open/close '''
    # to implement
    return
