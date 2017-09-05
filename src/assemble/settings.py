#!/usr/bin/env python3
# -*- coding: utf-8 -*-


'''
Settings for experiments
'''

from typing import List, Dict, Tuple, Callable, Iterable, NamedTuple, FrozenSet # pylint: disable=unused-import
import numpy as np
import assemble.data as data
import assemble.scaler as scaler

class BasePeakSetting: # pylint: disable=too-many-instance-attributes
    '''
    regroups information regarding oligo experiments
    '''
    def __init__(self,**kwa):
        self._pos:List[np.array]=[]
        self._fpos:np.array=np.empty(shape=(0,),dtype='f4') # flat
        self._seqs:List[Tuple[str, ...]]=[]
        self._fseqs:List[str]=[] # flat
        self._peaks:List[scaler.OPeakArray]=[]
        self._olis:List[data.OligoPeak]=[]
        self.min_overl:int=kwa.get("min_overl",2)
        self.unsigned:bool=kwa.get("unsigned",True)
        self.peakids:List[List[int]]=[]

    def set_peaks(self,value:scaler.OPeakArray):
        'update peaks and inner attr'
        self._peaks=value
        self._pos=[peak.posarr for peak in value]
        self._olis=[oli for peak in self._peaks for oli in peak.arr] # arbitrary order
        self._fpos=np.array([pos for peak in value for pos in peak.posarr])
        self._seqs=[peak.seqs for peak in value]
        self._fseqs=[seq for seqs in self._seqs for seq in seqs]
        self.peakids=[[self._olis.index(oli) for oli in peak.arr]
                      for peak in self._peaks] # not great imp.


    def get_peaks(self):
        'prop'
        return self._peaks

class PeakSetting(BasePeakSetting):
    '''
    regroups information regarding oligo experiments
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.peaks:List[scaler.OPeakArray]=kwa.get("peaks",[])

    @property
    def peaks(self):
        'prop'
        return self.get_peaks

    @peaks.setter
    def peaks(self,value:scaler.OPeakArray):
        self.set_peaks(value)

class ScaleSetting(PeakSetting):
    'adds boundaries information on stretch and bias to PeakSetting'
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.bstretch:scaler.Bounds=kwa.get("bstretch",scaler.Bounds())
        self.bbias:scaler.Bounds=kwa.get("bbias",scaler.Bounds())
        self.peaks:List[scaler.OPeakArray]=kwa.get("peaks",[])

class SpringSetting(ScaleSetting):
    '''
    adds Springs to the peaks
    if the noise is small and we rescale peaks kinter>kintra
    should the inter springs be directed? It should help
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.kintra:float=kwa.get("kintra",1)
        self.kinter:float=kwa.get("kinter",2)
        self.peaks:List[scaler.OPeakArray]=kwa.get("peaks",[])

    @property
    def peaks(self)->List[scaler.OPeakArray]:
        'prop'
        return self.get_peaks()

    @peaks.setter
    def peaks(self,peaks:List[scaler.OPeakArray]):
        'peaks setter'
        self.set_peaks(peaks)
