#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
need to allow for beads with only a subset of good cycles
need to add a little marker specifying when the data is loaded
Add a test : if min molextension is too big
'''

from typing import Set
import numpy
import pandas as pd
from utils.logconfig import getLogger

from ramp import RampModel, RampData


LOGS = getLogger(__name__)


class RampProcess:
    'all processing units'

    @staticmethod
    def zmag_close(data:RampData, reverse_time:bool = False)->pd.DataFrame:
        'estimate value of zmag to close the hairpin'
        if reverse_time:
            ids = data.dzdt[data.dzdt[data.det]<0].apply(lambda x:x.last_valid_index())
        else:
            ids = data.dzdt[data.dzdt[data.det]<0].apply(lambda x:x.first_valid_index())

        zmcl = pd.DataFrame(index = data.beads(), columns = range(data.ncycles))
        for bcid in ids.valid().index:
            zmcl.loc[bcid[0], bcid[1]] = data.dataz[("zmag", bcid[1])][ids[bcid]]

        return zmcl

    @staticmethod
    def zmag_open(data:RampData)->pd.DataFrame:
        'estimate value of zmag to open the hairpin'
        ids = data.dzdt[data.dzdt[data.det]>0].apply(lambda x:x.last_valid_index())
        zmop = pd.DataFrame(index = data.beads(), columns = range(data.ncycles))
        for bcid in ids.valid().index:
            zmop.loc[bcid[0], bcid[1]] = data.dataz[("zmag", bcid[1])][ids[bcid]]

        return zmop

    @staticmethod
    def _estZAtOpening(data:RampData)-> pd.Series:
        '''
        detect indices of changes in dzdt
        take the index preceding the first in dataz
        '''
        ids = data.dzdt[data.dzdt[data.det]>0].apply(lambda x:x.first_valid_index())
        ids = ids[data.bcids]
        zest = pd.Series([numpy.nan for i in ids.keys()], index = ids.keys())
        ids = ids[ids.notnull()]
        for k, val in ids.items():
            zest[k] = data.dataz[k][int(val - 1)]
        return zest

    @staticmethod
    def _estZWhenOpened(data)-> pd.Series:
        '''
        detect indices of changes in dzdt
        take the last index in dataz
        '''
        ids = data.dzdt[data.dzdt[data.det]>0].apply(lambda x:x.last_valid_index())
        ids = ids[data.bcids]
        zest = pd.Series([numpy.nan for i in ids.keys()], index = ids.keys())
        ids = ids[ids.notnull()]
        for k, val in ids.items():
            zest[k] = data.dataz[k][int(val)]
        return zest

    @staticmethod
    def detect_outliers(data:RampData,scale:float):
        '''detects opening and closing '''
        # quantile detection
        quant1 = data.dzdt.quantile(0.25)
        quant3 = data.dzdt.quantile(0.75)
        max_outlier = quant3+scale*(quant3-quant1)
        min_outlier = quant1-scale*(quant3-quant1)
        return (data.dzdt>max_outlier)|(data.dzdt<min_outlier)

    @staticmethod
    def keep_beadids(data:RampData,scale,bids:Set[int])->None:
        'pops all unwanted beads'

        data.bcids = [k for k in data.bcids if k[0] in bids]
        data.ncycles = max(i[1] for i in data.bcids) +1

        keys = [k for k in data.dataz.keys() if not isinstance(k[0],int)]
        keys += data.bcids
        data.dataz = data.dataz[keys]
        data.dzdt = data.dzdt[keys]
        data.det = RampProcess.detect_outliers(data,scale)

    @staticmethod
    def are_good_bead_cycle(data): # ok as is
        '''
        Test for each (bead,cycle) if an opening is detected before a detected closing.
        If no opening or no closing are detected the returned corresponding results is False
        '''
        # last postive index
        lpos = data.dzdt[(data.det) & (data.dzdt>0)].apply(lambda x: x.last_valid_index())

        # first negative index
        fneg = data.dzdt[(data.det) & (data.dzdt<0)].apply(lambda x: x.first_valid_index())

        # if no pos (neg) are detected lpos (fneg) is None and (fneg-lpos)>0 is always False
        keep = (fneg-lpos)>0

        return keep

    @staticmethod
    def get_good_beadids(model:RampModel,data:RampData)->Set[int]:
        '''
        returns the set of beads selected by _isGoodBead
        All cycles of a bead  must match the conditions for qualification as good bead.
        This condition may be too harsh for some track files (will improve).
        '''
        are_good = RampProcess.are_good_bead_cycle()
        pbead = {bead:[bcid for bcid in data.bcids if bcid[0]==bead] for bead in data.beads()}
        gpbead = {bead:[bc for bc in bcids if are_good[bc]] for bead,bcids in pbead.items()}
        goods ={i for i in data.beads() if len(gpbead[i])/len(pbead[i])>model.good_ratio}
        goods = goods & data._beadIdsCorr2zmag(toconsider = goods)
        return goods - self.getFixedBeadIds() - self.noBeadCrossIds()

    
    def clean(self):
        '''good beads open and close with zmag
        '''
        goods = self.getGoodBeadIds()
        self.keepBeadIds(goods)


    
    def noBeadCrossIds(self)->set:
        '''
        returns cross ids who does not have a match with a bead
        '''
        # could do with more thorough testing but a couple of checks showed correct behaviour
        corrids = self._beadIdsCorr2zmag(toconsider = None)
        return {i for i in self.beads() if i not in corrids}

    
    def _estimateZPhase3(self):
        ''' estimate the z value corresponding to phase 3 (i.e. highest value of zmag)
        '''
        return self.dataz[self.bcids].apply(
            lambda x:x.rolling(window=self.model.window,center=True).median()).max()

    
    def _estimateZPhase1(self):
        ''' estimate the z value corresponding to phase 1
        (i.e. lower value of zmag IN CASE OF RAMP ANALYSIS)
        '''
        return self.dataz[self.bcids].apply(
            lambda x:x.rolling(window=self.model.window,center=True).median()).min()

    
    def _estimateUnitScale(self)->int:
        '''
        uses information on zmag to find the smallest interval overwhich no changes occur in zmag
        assumes that phase3 is the smallest (this assumption could be removed)
        '''
        maxzm = max(self.dataz[self.zmagids()].max())
        scale = numpy.median([(self.dataz[zm]==maxzm).sum() for zm in self.zmagids()])
        return scale


    
    def getFixedBeadIds(self)->set:
        '''
        returns set of bead ids considered fixed
        could be modified to use estExtHPsize instead of dataz
        '''
        # check that the bead never opens
        closed = (self.dataz[self.bcids].max()-self.dataz[self.bcids].min()) <self.model.getMinExt()
        clids = {i[0] for i in self.bcids if\
                 all([closed[bcid] for bcid in self.bcids if bcid[0]==i[0]]) }
        return self._beadIdsCorr2zmag(toconsider = clids)


    
    def _beadIdsCorr2zmag(self,toconsider:set=None):
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
            if all(corr[(bid,cid)][("zmag",cid)]>self.model.corrThreshold
                   for cid in range(self.ncycles) ):
                beadids.append(bid)

        return set(beadids)


    
    def estExtHPsize(self):
        ''' estimates the size of the extended HP
        diff of z before opening () to its value in phase 3'''
        zph3 = self._estimateZPhase3()

        zop = self._estZAtOpening()
        return zph3-zop

    
    def estHPsize(self)->pd.DataFrame:
        ''' estimates HP size before extension
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



