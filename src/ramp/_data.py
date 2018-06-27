#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''Small library for computing ramp characteristics : zmag open, zmag close
needs more structure
need to allow for beads with only a subset of good cycles
need to add a little marker specifying when the data is loaded
Add a test : if min molextension is too big
'''
from typing import Optional, Tuple , List
import pandas as pd
from data import Track
from utils.logconfig import getLogger

from ._model import RampModel
from ._process import RampProcess

LOGS = getLogger(__name__)

class RampData: # pylint: disable=too-many-public-methods
    '''sets up ramp analysis using RampModel for parametrisation'''

    def __init__(self, **kwargs) -> None:
        self.dataz = kwargs.get("data", None)
        self.model = kwargs.get("model", None)
        self.dzdt:Optional[pd.DataFrame] = None
        self.bcids:List[Tuple[int,int]] = None
        self.ncycles:int = None
        self.det:Optional[pd.DataFrame] = None
        if self.dataz is not None :
            self._setup()
            if self.model is not None :
                self.det = RampProcess.detect_outliers(self,self.model.scale)

    @classmethod
    def open_track(cls,trk,model:RampModel):
        ''' creates ramp from track
        '''
        trkd = Track(path = trk) if isinstance(trk,str) else trk
        return cls(data = pd.DataFrame({k:pd.Series(v) for k, v in dict(trkd.cycles).items()})
                   , model = model)

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

    def set_track(self,trk):
        '''
        changes the data using trk
        '''
        trkd = Track(path = trk) if isinstance(trk,str) else trk
        self.dataz = pd.DataFrame({k:pd.Series(v) for k, v in dict(trkd.cycles).items()})
        self._setup()
        if self.model is not None :
            self.det = RampProcess.detect_outliers(self,self.model.scale)

    def _setup(self):
        self.dzdt = self.dataz.rename_axis(lambda x:x-1)-self.dataz.rename_axis(lambda x:x+1)
        self.bcids = [k for k in self.dzdt.keys() if isinstance(k[0], int)]
        self.ncycles = max(i[1] for i in self.bcids) +1
