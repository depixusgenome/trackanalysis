#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
subdivise this file into Opening/closing processors, and good, fixed and bad bead detection
'''

from typing import Set, List, Dict, cast
import numpy
import pandas as pd

from ramp import RampModel, RampData
# needs change: data also includes its own model

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
    def are_good_bead_cycle(data):
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
        are_good = RampProcess.are_good_bead_cycle(data)
        pbead = {bead:[bcid for bcid in data.bcids if bcid[0]==bead] for bead in data.beads()}
        gpbead = {bead:[bc for bc in bcids if are_good[bc]] for bead,bcids in pbead.items()}
        goods ={i for i in data.beads() if len(gpbead[i])/len(pbead[i])>model.good_ratio}
        goods = goods & RampProcess._beadids_corr2zmag(model,data,toconsider=goods)
        out=goods-RampProcess.get_fixed_beadids(model,data)
        return out-RampProcess.no_bead_cross_ids(model,data)


    @staticmethod
    def clean(model:RampModel,data:RampData)->None:
        'good beads open and close with zmag'
        goods = RampProcess.get_good_beadids(model,data)
        RampProcess.keep_beadids(data,model.scale,goods)


    @staticmethod
    def no_bead_cross_ids(model:RampModel,data:RampData)->Set[int]:
        'returns cross ids who does not have a match with a bead'
        corrids=RampProcess._beadids_corr2zmag(model,data,toconsider=None)
        return {i for i in data.beads() if i not in corrids}

    @staticmethod
    def _est_zphase3(model:RampModel,data:RampData):
        'estimate the z value corresponding to phase 3 (i.e. highest value of zmag)'
        return data.dataz[data.bcids].apply(
            lambda x:x.rolling(window=model.window,center=True).median()).max()

    @staticmethod
    def _est_zphase1(model:RampModel,data:RampData):
        ''' estimate the z value corresponding to phase 1
        (i.e. lower value of zmag IN CASE OF RAMP ANALYSIS)
        '''
        return data.dataz[data.bcids].apply(
            lambda x:x.rolling(window=model.window,center=True).median()).min()

    @staticmethod
    def _est_unitscale(data:RampData)->int:
        '''
        uses information on zmag to find the smallest interval overwhich no changes occur in zmag
        assumes that phase3 is the smallest (this assumption could be removed)
        '''
        maxzm = max(data.dataz[data.zmagids()].max())
        scale = numpy.median([(data.dataz[zm]==maxzm).sum() for zm in data.zmagids()])
        return scale


    @staticmethod
    def get_fixed_beadids(model:RampModel,data:RampData)->Set[int]:
        '''
        returns set of bead ids considered fixed
        could be modified to use estExtHPsize instead of dataz
        '''
        # check that the bead never opens
        closed = (data.dataz[data.bcids].max()-data.dataz[data.bcids].min())\
                 <model.getminext()
        clids = {i[0] for i in data.bcids if\
                 all([closed[bcid] for bcid in data.bcids if bcid[0]==i[0]]) }
        return RampProcess._beadids_corr2zmag(model,data,toconsider = clids)


    @staticmethod
    def _beadids_corr2zmag(model:RampModel,data:RampData,toconsider:Set[int]=None)->Set[int]:
        '''
        returns the list of bead ids whose z value correlates with zmag for each cycle
        '''
        if toconsider is None:
            toconsider = data.beads()
            dataz = data.dataz
        else:
            # why is "zmag" not in keys
            dataz = data.dataz[[bcid for bcid in data.dataz.keys()
                                if bcid[0] in toconsider or isinstance(bcid[0],str)]]


        corr = dataz.corr()
        beadids=[]
        for bid in cast(set, toconsider):
            if all(corr[(bid,cid)][("zmag",cid)]>model.corrthreshold
                   for cid in range(data.ncycles) ):
                beadids.append(bid)

        return set(beadids)

    @staticmethod
    def est_ext_hpsize(model:RampModel,data:RampData):
        ''' estimates the size of the extended HP
        diff of z before opening () to its value in phase 3'''
        zph3 = RampProcess._est_zphase3(model,data)

        zop = RampProcess._estZAtOpening(data)
        return zph3-zop

    @staticmethod
    def est_hpsize(data:RampData)->pd.DataFrame:
        ''' estimates HP size before extension
        from z before opening () to its value when opened but before stretching
        bead ids are rows and cycleids are in column
        '''
        diff_op = RampProcess._estZWhenOpened(data) - RampProcess._estZAtOpening(data)
        nbeads = len(data.beads())
        size_est = pd.DataFrame({i:[numpy.nan]*nbeads\
                                  for i in range(data.ncycles)}, index = data.beads())
        for key,val in diff_op.items():
            size_est.loc[key[0],key[1]]=val
        return size_est

    @staticmethod
    def can_be_structure_event(data:RampData):
        'returns a boolean map. True if a plateau in z(t) is detected. False otherwise.'
        se_map = data.dzdt[(data.det) & (data.dzdt<0)].apply(RampProcess._se_map)
        return (se_map) & (~data.det) # pylint: disable=invalid-unary-operand-type

    @staticmethod
    def z_blockings(data:RampData):
        'for each bead, return the values of z where a blocking has occured'
        se_map = RampProcess.can_be_structure_event(data)
        return data.dataz[se_map]

    @staticmethod
    def count_z_blockings(data:RampData):
        '''
        returns a value of z and the number of times the bead has blocked at this value.
        Questions : can we use this differentiate between hairpins ?
        If this is provides a way to fingerprint the hairpin then
        we can use this to align the different cycles (replacement to phase 5 alignement
        (optimistic))
        '''
        # over estimating each z counts
        # take the histogram of each cycles, if there is overlap between bins, merge
        zvalues:Dict[int,List[float]] = {i:[] for i in data.beads()}
        zblocks = RampProcess.z_blockings(data)
        for bcid in data.bcids:
            zvalues[bcid[0]].extend(zblocks[bcid].dropna().values)
        return [numpy.array(zvalues[i]) for i in zvalues.keys()]

    @staticmethod
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
        return (data.index> fid) & (data.index<lid)
