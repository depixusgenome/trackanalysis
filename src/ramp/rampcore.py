#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Small library for computing ramp characteristics : zmag open, zmag close
needs more structure
need to allow for beads with only a subset of good cycles
need to add a little marker specifying when the data is loaded
Add a test : if min molextension is too big
'''
from typing import Optional, Tuple , Set, List # pylint: disable=unused-import
import numpy
import pandas as pd
from data import Track

from utils.logconfig import getLogger

LOGS = getLogger(__name__)

class RampModel:
    ''' holds instruction to handle the data
    If values change in the Model the Controller must be notified and act accordingly
    '''
    def __init__(self, **kwargs):
        self.scale = 10.0
        self.needscleaning = False
        self.corrthreshold = 0.5 # if above then correlation
        self._minext = kwargs.get("minextension",0.0)
        self.window = 7
        self._zclthreshold = kwargs.get("zclthreshold",None)
        self.good_ratio = kwargs.get("good_ratio",0.8) # if good_cycles/cycles above, then good

    def set_zclthreshold(self,value):
        '''
        sets _zclthreshold
        if _minExt is changed call controller and apply changes in RampData
        '''
        self._zclthreshold = value

    def get_zclthreshold(self):
        '''
        returns  _zclthreshold
        '''
        return self._zclthreshold

    def set_minext(self,value):
        '''
        set _minExt
        if _minExt is changed call controller and apply changes in RampData
        '''
        self._minext = value

    def getminext(self):
        '''
        Returns _minExt value.
        Warns User if _minExt has not be set.
        '''
        return self._minext

class RampData: # pylint: disable=too-many-public-methods
    '''sets up ramp analysis using RampModel for parametrisation'''

    def __init__(self, **kwargs) -> None:
        self.dataz = kwargs.get("data", None)
        self.model = kwargs.get("model", None)
        self.dzdt = None # type: Optional[pd.DataFrame]
        self.bcids = None # type: List[Tuple[int,int]]
        self.ncycles = None # type: int
        self.det = None # type: Optional[pd.DataFrame]
        self.track = kwargs.get("track", None)
        if self.dataz is not None :
            self._setup()
            if self.model is not None :
                self.det = detectoutliers(self.dzdt,self.model.scale)

    @classmethod
    def opentrack(cls,trk,model:RampModel):
        ''' creates ramp from track
        '''
        trkd = Track(path = trk, beadsonly = False) if isinstance(trk,str) else trk

        return cls(data = pd.DataFrame({k:pd.Series(v) for k, v in dict(trkd.cycles).items()}),
                   model = model,
                   track = trkd)


    def beads(self)->set:
        '''
        returns the set of bead ids
        '''
        return {i[0] for i in self.bcids}

    def zmagids(self):
        '''
        returns all pairs (zmag,cycleid)
        '''
        return [k for k in self.dzdt.keys() if k[0] == "zmag"]

    def tids(self):
        '''
        returns all pairs (time,cycleid)
        '''
        return [k for k in self.dzdt.keys() if k[0] == "t"]

    def settrack(self,trk):
        '''
        changes the data using trk
        '''
        trkd = Track(path = trk, beadsonly = False) if isinstance(trk,str) else trk
        self.track = trkd
        self.dataz = pd.DataFrame({k:pd.Series(v) for k, v in dict(trkd.cycles).items()})
        self._setup()
        if self.model is not None :
            self.det = detectoutliers(self.dzdt,self.model.scale)

    def _setup(self):
        self.dzdt = self.dataz.rename_axis(lambda x:x-1)-self.dataz.rename_axis(lambda x:x+1)
        self.bcids = [k for k in self.dzdt.keys() if isinstance(k[0], int)]
        self.ncycles = max(i[1] for i in self.bcids) +1

    def zmagclose(self, reverse_time:bool = False):
        '''estimate value of zmag to close the hairpin'''
        if reverse_time:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.last_valid_index())
        else:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.first_valid_index())

        zmcl = pd.DataFrame(index = self.beads(), columns = range(self.ncycles))
        for bcid in ids.valid().index: # use enumerate
            zmcl.loc[bcid[0], bcid[1]] = self.dataz[("zmag", bcid[1])][ids[bcid]]

        return zmcl


    def zmagopen(self):
        ''' estimate value of zmag to open the hairpin'''
        ids = self.dzdt[self.dzdt[self.det]>0].apply(lambda x:x.last_valid_index())
        zmop = pd.DataFrame(index = self.beads(), columns = range(self.ncycles))
        for bcid in ids.valid().index:
            zmop.loc[bcid[0], bcid[1]] = self.dataz[("zmag", bcid[1])][ids[bcid]]

        return zmop

    def _estzatopening(self)-> pd.Series:
        '''
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

    def _estzwhenopened(self)-> pd.Series:
        '''
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

    def keepbeadids(self,bids:set)->None:
        '''
        pops all unwanted beads
        '''

        self.bcids = [k for k in self.bcids if k[0] in bids]
        self.ncycles = max(i[1] for i in self.bcids) +1

        keys = [k for k in self.dataz.keys() if not isinstance(k[0],int)]
        keys += self.bcids
        self.dataz = self.dataz[keys]
        self.dzdt = self.dzdt[keys]
        self.det = detectoutliers(self.dzdt,self.model.scale)


    def getgoodbeadids(self)->set:
        '''
        returns the list of beads selected by _isGoodBead
        All cycles of a bead  must match the conditions for qualification as good bead.
        This condition may be too harsh for some track files (will improve).
        '''
        are_good = self.aregoodbeadcycle()
        pbead = {bead:[bcid for bcid in self.bcids if bcid[0]==bead] for bead in self.beads()}
        gpbead = {bead:[bc for bc in bcids if are_good[bc]] for bead,bcids in pbead.items()}
        goods ={i for i in self.beads() if len(gpbead[i])/len(pbead[i])>self.model.good_ratio}
        goods = goods & self._beadidscorr2zmag(toconsider = goods)
        return goods - self.getfixedbeadids() - self.nobeadcrossids()

    def clean(self):
        '''good beads open and close with zmag
        '''
        goods = self.getgoodbeadids()
        self.keepbeadids(goods)

    def aregoodbeadcycle(self): # ok as is
        '''
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

    def nobeadcrossids(self)->set:
        '''
        returns cross ids who does not have a match with a bead
        '''
        # could do with more thorough testing but a couple of checks showed correct behaviour
        corrids = self._beadidscorr2zmag(toconsider = None)
        return {i for i in self.beads() if i not in corrids}

    def _estimatezphase3(self):
        ''' estimate the z value corresponding to phase 3 (i.e. highest value of zmag)
        '''
        return self.dataz[self.bcids].apply(
            lambda x:x.rolling(window=self.model.window,center=True).median()).max()

    def _estimatezphase1(self):
        ''' estimate the z value corresponding to phase 1
        (i.e. lower value of zmag IN CASE OF RAMP ANALYSIS)
        '''
        return self.dataz[self.bcids].apply(
            lambda x:x.rolling(window=self.model.window,center=True).median()).min()

    def _estimateunitscale(self)->int:
        '''
        uses information on zmag to find the smallest interval overwhich no changes occur in zmag
        assumes that phase3 is the smallest (this assumption could be removed)
        '''
        maxzm = max(self.dataz[self.zmagids()].max())
        scale = numpy.median([(self.dataz[zm]==maxzm).sum() for zm in self.zmagids()])
        return scale


    def getfixedbeadids(self)->set:
        '''
        returns set of bead ids considered fixed
        could be modified to use estExtHPsize instead of dataz
        '''
        # check that the bead never opens
        closed = (self.dataz[self.bcids].max()-self.dataz[self.bcids].min()) <self.model.getminext()
        clids = {i[0] for i in self.bcids if\
                 all([closed[bcid] for bcid in self.bcids if bcid[0]==i[0]]) }
        return self._beadidscorr2zmag(toconsider = clids)


    def _beadidscorr2zmag(self,toconsider:set=None):
        '''
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
            if all(corr[(bid,cid)][("zmag",cid)]>self.model.corrthreshold
                   for cid in range(self.ncycles) ):
                beadids.append(bid)

        return set(beadids)


    def estexthpsize(self):
        ''' estimates the size of the extended HP
        diff of z before opening () to its value in phase 3'''
        zph3 = self._estimatezphase3()

        zop = self._estzatopening()
        return zph3-zop

    def esthpsize(self):
        ''' estimates HP size before extension
        from z before opening () to its value when opened but before stretching
        bead ids are rows and cycleids are in column
        '''
        diff_op = self._estzwhenopened() - self._estzatopening()
        nbeads = len(self.beads())
        size_est = pd.DataFrame({i:[numpy.nan]*nbeads\
                                  for i in range(self.ncycles)}, index = self.beads())
        for key,val in diff_op.items():
            size_est.loc[key[0],key[1]]=val
        return size_est

    def can_be_structure_event(self):
        '''
        returns a boolean map. True if a plateau in z(t) is detected. False otherwise.
        '''
        se_map = self.dzdt[(self.det) & (self.dzdt<0)].apply(_se_map)
        return (se_map) & (~self.det) # pylint: disable=invalid-unary-operand-type

    def z_blockings(self):
        '''
        for each bead, return the values of z where a blocking has occured
        '''
        se_map = self.can_be_structure_event()
        return self.dataz[se_map]

    def count_z_blockings(self):
        '''
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
    '''
    To finish
    returns the list of continuous indices.
    e.g: [2,3,7,8,9,10] returns [[2,3],[7,10]]
    '''
    ite=ser[0]
    while ite!=ser[-1]:
        boud=[ite]

    return boud

def map_boundaries(bdata:pd.DataFrame):
    '''
    To finish
    If bdata is a data frame which contains cluster of True values
    returns the boundaries of these clusters
    '''
    indices = bdata.apply(lambda x:pd.Series(x.dropna().index))
    # apply dbscan algorithm with eps=1, min_samples=1

    return indices

def probability_false_positive(data:RampData):
    '''
    To finish
    For each bead compute the probability (frequentist approach) of observing a
    blocking during the ramp stage
    '''

    return data

def cluster1D_dbscan(values,eps=0.2,min_samples=3,**kwargs):
    '''
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
        LOGS.error(err)

    return dbscan(values.reshape(-1,1),
                  eps=eps,
                  min_samples=min_samples,
                  **kwargs)[1]


def _se_map(data:pd.Series):
    '''
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


def detectoutliers(dzdt,scale:float):
    '''detects opening and closing '''
    # quantile detection
    quant1 = dzdt.quantile(0.25)
    quant3 = dzdt.quantile(0.75)
    max_outlier = quant3+scale*(quant3-quant1)
    min_outlier = quant1-scale*(quant3-quant1)
    return (dzdt>max_outlier)|(dzdt<min_outlier)
