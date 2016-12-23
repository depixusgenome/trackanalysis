#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''Small library for computing ramp characteristics : zmag open, zmag close
needs more structure
need to allow for beads with only a subset of good cycles
need to add a little marker specifying when the data is loaded
Add a test : if min molextension is too big
'''
import functools
from typing import Optional, Tuple , Set # pylint: disable=unused-import
import warnings
import numpy
import pandas as pd # type: ignore
from data import Track

class RampModel:
    u''' holds instruction to handle the data
    If values change in the Model the Controller must be notified and act accordingly
    '''
    def __init__(self, **kwargs):
        self.scale = 5.0
        self.needsCleaning = False
        self.corrThreshold = 0.5
        self._minExt = None
        self.window = 5
        if "minExtension" in kwargs:
            self._minExt=kwargs["minExtension"]

    def setMinExt(self,value):
        u'''
        set _minExt
        if _minExt is changed call controller and apply changes in RampData
        '''
        self._minExt = value

    def getMinExt(self):
        u'''
        Returns _minExt value.
        Warns User if _minExt has not be set.
        '''
        if self._minExt is None:
            warnings.warn(UserWarning("minimal extension minExt has no value assigned"))
        return self._minExt

class RampTask:
    u'''
    will define a set of action called by RampController
    '''
    pass
class RampController:
    u'''
    will dictate changes to RampData relative to a ramp
    '''
    pass

class RampData:
    u'''sets up ramp analysis using RampModel for parametrisation'''

    def __init__(self, **kwargs) -> None:
        self.dataz = kwargs.get("data", None)
        self.model = kwargs.get("model", None)
        self.dzdt = None # type: Optional[pd.DataFrame]
        self.bcids = None # type: Set[Tuple[int,int]]
        self.ncycles = None # type: int
        self.det = None # type: Optional[pd.DataFrame]
        if self.dataz is not None :
            self._setup()
            if self.model is not None :
                self.det = detectOutliers(self.dzdt,self.model.scale)

    @classmethod
    def openTrack(cls,trk,model:RampModel):
        u''' creates ramp from track
        '''
        trkd = Track(path = trk) if isinstance(trk,str) else trk
        return cls(data = pd.DataFrame({k:pd.Series(v) for k, v in dict(trkd.cycles).items()})
                   , model = model)


    def beads(self)->set:
        u'''
        returns the set of bead ids
        '''
        return {i[0] for i in self.bcids}
    def zmagids(self):
        u'''
        returns all pairs (zmag,cycleid)
        '''
        return [k for k in self.dzdt.keys() if k[0] == "zmag"]

    def tids(self):
        u'''
        returns all pairs (time,cycleid)
        '''
        return [k for k in self.dzdt.keys() if k[0] == "t"]

    def setTrack(self,trk):
        u'''
        changes the data using trk
        '''
        trkd = Track(path = trk) if isinstance(trk,str) else trk
        self.dataz = pd.DataFrame({k:pd.Series(v) for k, v in dict(trkd.cycles).items()})
        self._setup()
        if self.model is not None :
            self.det = detectOutliers(self.dzdt,self.model.scale)

    def _setup(self):
        self.dzdt = self.dataz.rename_axis(lambda x:x-1)-self.dataz.rename_axis(lambda x:x+1)
        self.bcids = {k for k in self.dzdt.keys() if isinstance(k[0], int)}
        self.ncycles = max(i[1] for i in self.bcids) +1

    def zmagClose(self, reverse_time:bool = False):
        u'''estimate value of zmag to close the hairpin'''
        if reverse_time:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.last_valid_index())
        else:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.first_valid_index())

        zmcl = pd.DataFrame(index = self.beads(), columns = range(self.ncycles))
        for bcid in ids.valid().index:
            zmcl.loc[bcid[0], bcid[1]] = self.dataz[("zmag", bcid[1])][ids[bcid]]

        return zmcl


    def zmagOpen(self)->pd.DataFrame:
        u''' estimate value of zmag to open the hairpin'''
        ids = self.dzdt[self.dzdt[self.det]>0].apply(lambda x:x.last_valid_index())
        zmop = pd.DataFrame(index = self.beads(), columns = range(self.ncycles))
        for bcid in ids.valid().index:
            zmop.loc[bcid[0], bcid[1]] = self.dataz[("zmag", bcid[1])][ids[bcid]]

        return zmop

    def _estZAtOpening(self)-> pd.Series:
        u'''
        detect indices of changes in dzdt
        take the previous index in dataz
        '''
        ids = self.dzdt[self.dzdt[self.det]>0].apply(lambda x:x.first_valid_index())
        ids = ids[list(self.bcids)]
        zest = pd.Series([numpy.nan for i in ids.keys()], index = ids.keys())
        ids = ids[ids.notnull()]
        for k, val in ids.items():
            zest[k] = self.dataz[k][int(val - 1)]
        return zest

    def keepBeadIds(self,bids:set)->None:
        u'''
        pops all unwanted beads
        '''

        self.bcids = {k for k in self.bcids if k[0] in bids}
        self.ncycles = max(i[1] for i in self.bcids) +1

        keys = [k for k in self.dataz.keys() if not isinstance(k[0],int)]
        keys += list(self.bcids)
        self.dataz = self.dataz[keys]
        self.dzdt = self.dzdt[keys]
        self.det = detectOutliers(self.dzdt,self.model.scale)


    def getGoodBeadIds(self)->set:
        u'''
        rewrite to be faster
        returns the list of beads selected by _isGoodBead
        All cycles of a bead  must match the conditions for qualification as good bead.
        This condition may be too harsh for some track files (will improve).
        '''
        are_good = self.areGoodBeadCycle()
        todel = {i[0] for i in self.bcids if not are_good[i]} # harsh

        return {i for i in self.beads() if i not in todel}

    def clean(self):
        u'''good beads open and close with zmag
        '''
        goods = self.getGoodBeadIds()
        self.keepBeadIds(goods)

    def areGoodBeadCycle(self): # ok as is
        u'''
        Test for each (bead,cycle) if an opening is detected before a detected closing.
        If no opening or no closing are detected the returned corresponding results is False
        '''
        # last postive index
        lpos = self.dzdt[(self.det) & (self.dzdt>0)].apply(lambda x: x.last_valid_index())

        # first negative index
        fneg = self.dzdt[(self.det) & (self.dzdt<0)].apply(lambda x: x.first_valid_index())

        # if no pos (neg) are detected lpos (fneg) is None and (fneg-lpos)>0 is always False
        keep = (fneg-lpos)>0

        return keep



    def noBeadCrossIds(self)->set:
        u'''
        returns cross ids who does not have a match with a bead
        '''
        # could do with more thorough testing but a couple of checks showed correct behaviour
        corrids = self._beadIdsCorr2zmag(toconsider = None)
        return {i for i in self.beads() if i not in corrids}

    def _estimateZPhase3(self):
        u''' estimate the z value corresponding to phase 3
        '''

        return self.dataz[list(self.bcids)].apply(
            lambda x:x.rolling(window=self.model.window,center=True).median()).max()

    def _estimateUnitScale(self)->int:
        u'''
        uses information on zmag to find the smallest interval overwhich no changes occur in zmag
        assumes that phase3 is the smallest (this assumption could be removed)
        '''
        maxzm = max(self.dataz[self.zmagids()].max())

        scale = numpy.median([(self.dataz[zm]==maxzm).sum() for zm in self.zmagids()])
        return scale


    def getFixedBeadIds(self)->set:
        u'''
        returns set of bead ids considered fixed
        must be modified to use estMolExt instead of dataz
        '''
        # check that the bead never opens
        closed = self.dataz < self.model.getMinExt()
        clids = {i[0] for i in self.bcids if all(closed[i]) }
        return self._beadIdsCorr2zmag(toconsider = clids)


    def _beadIdsCorr2zmag(self,toconsider:set=None):
        u'''
        returns the list of bead ids whose z value correlates with zmag for each cycle
        to check
        '''

        if toconsider is None:
            toconsider = self.beads()
            data = self.dataz
        else:
            # why is "zmag" not in keys
            data = self.dataz[[bcid for bcid in self.dataz.keys()
                               if bcid[0] in toconsider or isinstance(bcid[0],str)]]


        corr = data.corr()
        beadids=[]
        for bid in toconsider:
            if all(corr[(bid,cid)][("zmag",cid)]>self.model.corrThreshold
                   for cid in range(self.ncycles) ):
                beadids.append(bid)

        return set(beadids)


    def estMolExt(self):
        u''' estimates molecule extension from z
        before opening () to its value in phase 3'''
        zph3 = self._estimateZPhase3()

        zop = self._estZAtOpening()
        return zph3-zop


class Dubious:
    u'''
    decorator for dubious function
    '''
    def __init__(self,msg):
        self.count=1
        self.msg=msg
    def __call__(self,fcn):
        functools.wraps(fcn)
        def wrapper(*args,**kwargs):
            u'''
            decorates a function whose use is dubious
            '''
            if self.count==1:
                print("function %s is dubious"%fcn.__name__)
                print(self.msg)
                self.count+=1
            return fcn(*args,**kwargs)
        return wrapper

NOTUSEFUL = Dubious("As is this function is not very useful")
OLDTOOSLOW = Dubious("function too slow and a faster alternative has been implemented")


@OLDTOOSLOW
def _isGoodBead(dzdt:pd.Series,scale:float):
    u'''test a single bead over a single cycle'''
    return _isGooddzdt(dzdt,scale)


@OLDTOOSLOW
def _isGooddzdt(dzdt:pd.Series,scale:float):
    u'''
    tests whether a bead opens and close using only information on dzdt
    '''
    det = detectOutliers(dzdt,scale)
    # at least one opening and closing
    if not (any(dzdt[det]>0) and any(dzdt[det]<0)):
        return False

    # last index of positive detected dzdt
    lposid = dzdt[(dzdt>0)&det].last_valid_index()
    negids = dzdt[(dzdt<0)&det].index
    return not any((negids-lposid)<0)


@NOTUSEFUL
def _isdzdt_unit_consistent(dzdt:pd.Series,scale:float,uscale:int)-> bool:
    u'''
    returns True if the interval between changes of sign of dzdt is > unit_scale
    False otherwise
    No proof that this test rejects more bead, cycles than the _isGooddzdt test..
    '''
    sign = dzdt.apply(lambda x : 1 if x>scale else -1 if x<-scale else 0)

    gen = (sign[i:i+uscale] for i in range(sign.size-uscale+1))
    for win in gen:
        if any(win)>0 and any(win)<0:
            return False
    return True

@NOTUSEFUL
def isGoodBeadCycle(dzdt:pd.Series, scale:float, unit_scale:int):
    u'''
    returns a pd.DataFrame which is a boolean applicable to data.dataz
    '''
    if not _isGooddzdt(dzdt,scale):
        return False
    return _isdzdt_unit_consistent(dzdt,scale,unit_scale)


def detectOutliers(dzdt,scale:float):
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
    pass

def fixedBead():
    u''' bead does not open/close '''
    # to implement
    pass

def fixedBeadIds():
    u'''
    returns the set of beads supposedly fixed :
    z correlated with zmag
    '''
    # to finish implementing
    # corr=self.dataz.corr()>self.model.corrThreshold
    # need more conditions to qualify as fixed bead
    pass


def can_be_structure_event(dzdt,detected):
    u'''
    args : dzdt and detected (output of detect_outliers(dzdt))
    '''
    # find when rezipping starts
    st_rezip = dzdt[dzdt[detected]<0].apply(lambda x: x.first_valid_index())
    # find when rezipping stops
    ed_rezip = dzdt[dzdt[detected]<0].apply(lambda x: x.last_valid_index())
    # create a map :
    # If not detected by the sanitising algorithm,
    # after z_closing (first dzdt[detected]>0,
    # and before last dzdt[detected]<0
    canbe_se = ~detected&dzdt.apply(
        lambda x:x.index>(st_rezip[x.name]))&dzdt.apply(lambda x:x.index<(ed_rezip[x.name]))

    return canbe_se

if __name__=="__main__":
    print("ramp called as main")
