#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u'''Small library for computing ramp characteristics : zmag open, zmag close
needs more structure
need to allow for beads with only a subset of good cycles
need to add a little marker specifying when the data is loaded
Add a test : if min molextension is too big
'''
import functools
from typing import Optional, Tuple , Set, List # pylint: disable=unused-import
import numpy
import pandas as pd
from data import Track

class RampModel:
    u''' holds instruction to handle the data
    If values change in the Model the Controller must be notified and act accordingly
    '''
    def __init__(self, **kwargs):
        self.scale = 5.0
        self.needsCleaning = False
        self.corrThreshold = 0.5 # if above then correlation
        self._minExt = kwargs.get("minExtension",0.0)
        self.window = 7
        self._zclthreshold = kwargs.get("zclthreshold",None)
        self.good_ratio = kwargs.get("good_ratio",0.8) # if good_cycles/cycles above, then good

    def set_zclthreshold(self,value):
        u'''
        sets _zclthreshold
        if _minExt is changed call controller and apply changes in RampData
        '''
        self._zclthreshold = value

    def get_zclthreshold(self):
        u'''
        returns  _zclthreshold
        '''
        return self._zclthreshold

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

class RampData: # pylint: disable=too-many-public-methods
    u'''sets up ramp analysis using RampModel for parametrisation'''

    def __init__(self, **kwargs) -> None:
        self.dataz = kwargs.get("data", None)
        self.model = kwargs.get("model", None)
        self.dzdt = None # type: Optional[pd.DataFrame]
        self.bcids = None # type: List[Tuple[int,int]]
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
        self.bcids = [k for k in self.dzdt.keys() if isinstance(k[0], int)]
        self.ncycles = max(i[1] for i in self.bcids) +1

    def zmagClose(self, reverse_time:bool = False):
        u'''estimate value of zmag to close the hairpin'''
        if reverse_time:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.last_valid_index())
        else:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.first_valid_index())

        zmcl = pd.DataFrame(index = self.beads(), columns = range(self.ncycles))
        for bcid in ids.valid().index: # use enumerate
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
        take the index preceding the first in dataz
        '''
        ids = self.dzdt[self.dzdt[self.det]>0].apply(lambda x:x.first_valid_index())
        ids = ids[self.bcids]
        zest = pd.Series([numpy.nan for i in ids.keys()], index = ids.keys())
        ids = ids[ids.notnull()]
        for k, val in ids.items():
            zest[k] = self.dataz[k][int(val - 1)]
        return zest

    def _estZWhenOpened(self)-> pd.Series:
        u'''
        detect indices of changes in dzdt
        take the last index in dataz
        '''
        ids = self.dzdt[self.dzdt[self.det]>0].apply(lambda x:x.last_valid_index())
        ids = ids[self.bcids]
        zest = pd.Series([numpy.nan for i in ids.keys()], index = ids.keys())
        ids = ids[ids.notnull()]
        for k, val in ids.items():
            zest[k] = self.dataz[k][int(val)]
        return zest

    def keepBeadIds(self,bids:set)->None:
        u'''
        pops all unwanted beads
        '''

        self.bcids = [k for k in self.bcids if k[0] in bids]
        self.ncycles = max(i[1] for i in self.bcids) +1

        keys = [k for k in self.dataz.keys() if not isinstance(k[0],int)]
        keys += self.bcids
        self.dataz = self.dataz[keys]
        self.dzdt = self.dzdt[keys]
        self.det = detectOutliers(self.dzdt,self.model.scale)


    def getGoodBeadIds(self)->set:
        u'''
        returns the list of beads selected by _isGoodBead
        All cycles of a bead  must match the conditions for qualification as good bead.
        This condition may be too harsh for some track files (will improve).
        '''
        are_good = self.areGoodBeadCycle()
        pbead = {bead:[bcid for bcid in self.bcids if bcid[0]==bead] for bead in self.beads()}
        gpbead = {bead:[bc for bc in bcids if are_good[bc]] for bead,bcids in pbead.items()}
        goods ={i for i in self.beads() if len(gpbead[i])/len(pbead[i])>self.model.good_ratio}
        return goods&self._beadIdsCorr2zmag(toconsider = goods)

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
        u''' estimate the z value corresponding to phase 3 (i.e. highest value of zmag)
        '''

        return self.dataz[self.bcids].apply(
            lambda x:x.rolling(window=self.model.window,center=True).median()).max()

    def _estimateZPhase1(self):
        u''' estimate the z value corresponding to phase 1
        (i.e. lower value of zmag IN CASE OF RAMP ANALYSIS)
        '''

        return self.dataz[self.bcids].apply(
            lambda x:x.rolling(window=self.model.window,center=True).median()).min()

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
        must be modified to use estExtHPsize instead of dataz
        '''
        # check that the bead never opens
        closed = (self.dataz[self.bcids].max()-self.dataz[self.bcids].min()) <self.model.getMinExt()
        clids = {i[0] for i in self.bcids if\
                 all([closed[bcid] for bcid in self.bcids if bcid[0]==i[0]]) }
        return self._beadIdsCorr2zmag(toconsider = clids)


    def _beadIdsCorr2zmag(self,toconsider:set=None):
        u'''
        returns the list of bead ids whose z value correlates with zmag for each cycle
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


    def estExtHPsize(self):
        u''' estimates the size of the extended HP
        diff of z before opening () to its value in phase 3'''
        zph3 = self._estimateZPhase3()

        zop = self._estZAtOpening()
        return zph3-zop

    def estHPsize(self)->pd.DataFrame:
        u''' estimates HP size before extension
        from z before opening () to its value when opened but before stretching
        bead ids are rows and cycleids are in column
        '''
        diff_op = self._estZWhenOpened() - self._estZAtOpening()
        nbeads = len(self.beads())
        size_est = pd.DataFrame({i:[numpy.nan]*nbeads\
                                  for i in range(self.ncycles)}, index = self.beads())
        for key,val in diff_op.items():
            size_est.loc[key[0],key[1]]=val
        return size_est


    def can_be_structure_event(self):
        u'''
        returns a boolean map. True if a plateau in z(t) is detected. False otherwise.
        '''
        se_map = self.dzdt[(self.det) & (self.dzdt<0)].apply(_se_map)
        return (se_map) & (~self.det)

    def z_blockings(self):
        u'''
        for each bead, return the values of z where a blocking has occured
        '''
        se_map = self.can_be_structure_event()
        return self.dataz[se_map]

    def count_z_blockings(self):
        u'''
        returns a value of z and the number of times the bead has blocked at this value.
        Questions : can we use this differentiate between hairpins ?
        If this is provides a way to fingerprint the hairpin then
        we can use this to align the different cycles (replacement to phase 5 alignement
        (optimistic))
        '''
        # over estimating each z counts
        # take the histogram of each cycles, if there is overlap between bins, merge
        zvalues = {i:[] for i in self.beads()}
        zblocks = self.z_blockings()
        for bcid in self.bcids:
            zvalues[bcid[0]].extend(zblocks[bcid].dropna().values)
        return [numpy.array(zvalues[i]) for i in zvalues.keys()]


def _continuous_indices(ser:pd.Series)->list:
    u'''
    To finish
    returns the list of continuous indices.
    e.g: [2,3,7,8,9,10] returns [[2,3],[7,10]]
    '''
    ite=ser[0]
    while ite!=ser[-1]:
        boud=[ite]

    return boud

def map_boundaries(bdata:pd.DataFrame)->pd.DataFrame:
    u'''
    To finish
    If bdata is a data frame which contains cluster of True values
    returns the boundaries of these clusters
    '''
    indices = bdata.apply(lambda x:pd.Series(x.dropna().index))
    # apply dbscan algorithm with eps=1, min_samples=1

    return indices

def probability_false_positive(data:RampData):
    u'''
    To finish
    For each bead compute the probability (frequentist approach) of observing a
    blocking during the ramp stage
    '''

    return data

def cluster1D_dbscan(values,eps=0.2,min_samples=3,**kwargs):
    u'''
    use DBSCAN algorithm to define clusters. Assumes a drop in density
    values is a numpy array of 1D-values
    applies the dbscan algorithm to cluster values
    handles the same optional arguments as sklearn.cluster.dbscan
    '''
    if values.size==0:
        return []
    try:
        from sklearn.cluster import dbscan
    except ImportError as err:
        print("Cannot import sklearn.cluster (not available on Windows).")
        print(err)
        print("returning")
    return dbscan(values.reshape(-1,1),
                  eps=eps,
                  min_samples=min_samples,
                  **kwargs)[1]


def _se_map(data:pd.Series):
    u'''
    return True for values whose index>first_valid_index()
    and index<last_valid_index()
    '''
    fid = data.first_valid_index()
    if fid is None:
        fid = data.index[-1]
    lid = data.last_valid_index()
    if lid is None:
        lid = data.index[0]
    return (data.index> fid) &\
        (data.index<lid)

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

@OLDTOOSLOW
def obsolete_can_be_structure_event(dzdt,detected):
    u'''
    args : dzdt and detected (output of detect_outliers(dzdt))
    Need to apply this to the full data set and not on each cycle
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
