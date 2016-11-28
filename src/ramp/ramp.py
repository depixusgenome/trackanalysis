import pandas as pd
import numpy
from data import Track

class RampModel():
    u''' holds instruction to handle the data'''
    def __init__(self): 
        self.scale = 5.0
        self.needsCleaning = True
       
class RampControler():
    u'''sets up ramp analysis using RampModel for parametrisation'''
    def __init__(self, datf:pd.DataFrame, model:RampModel):
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
        u'''  '''
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

        self.det = _detectOutliers(self.dzdt,self.model.scale)
        

    def zmagClose(self, reverse_time:bool = False):
        u'''estimate value of zmag to close the hairpin'''
        if reverse_time:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.last_valid_index())    
        else:
            ids = self.dzdt[self.dzdt[self.det]<0].apply(lambda x:x.first_valid_index())

        zmcl = pd.DataFrame(index = self.beads, columns = range(self.ncycles))
        for bcid in self.bcids:
            zmcl.loc[bcid[0], bcid[1]] = self.dataz[("zmag", bcid[1])][ids[bcid]] if numpy.isfinite(ids[bcid]) else numpy.nan
            
        return zmcl


    def zmagOpen(self)->pd.DataFrame:
        u''' estimate value of zmag to open the hairpin'''
        ids = self.dzdt[self.dzdt[self.det]>0].apply(lambda x:x.last_valid_index())    
        zmop = pd.DataFrame(index = self.beads, columns = range(self.ncycles))
        for bcid in self.bcids:
            zmop.loc[bcid[0], bcid[1]] = self.dataz[("zmag", bcid[1])][ids[bcid]] if numpy.isfinite(ids[bcid]) else numpy.nan

        return zmop

    def stripBadBeads(self):
        u'''good beads open and close with zmag'''
        good = self.dzdt.apply(lambda x: _isGoodBead(x,scale = self.model.scale))
        todel = {k[0] for k in self.bcids if not good[k]}
        keys = [k for k in self.dataz.keys() if k[0] not in todel]

        self.dataz = self.dataz[keys]
        self.dzdt = self.dzdt[keys]
        self.bcids = {k for k in self.dzdt.keys() if isinstance(k[0], int)}
        self.beads = {i[0] for i in self.bcids}
        self.ncycles = max(i[1] for i in self.bcids) +1
        return 

    
    
def _isGoodBead(dzdt:pd.Series,scale:int):
    u'''test a single bead over a single cycle'''
    det = _detectOutliers(dzdt,scale)
    # at least one opening and closing
    if not (any(dzdt[det]>0) and any(dzdt[det]<0)):
        return False
    
    # last index of positive detected dzdt
    lposid = dzdt[(dzdt>0)&det].last_valid_index()
    negids = dzdt[(dzdt<0)&det].index
    
    return not any((negids-lposid)<0)


def _detectOutliers(dzdt,scale:int):
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



    

"""
def can_be_structure_event(dz, detected):
    u'''
    args : dz and detected (output of detect_outliers(dz))
    '''
    # find when rezipping starts
    st_rezip = dz[dz[detected]<0].apply(lambda x: x.first_valid_index())
    # find when rezipping stops
    ed_rezip = dz[dz[detected]<0].apply(lambda x: x.last_valid_index())
    # create a map : 
    # If not detected by the sanitising algorithm, 
    # after z_closing (first dz[detected]>0, 
    # and before last dz[detected]<0
    canbe_se = ~detected&dz.apply(lambda x:x.index>(st_rezip[x.name]))&dz.apply(lambda x:x.index<(ed_rezip[x.name]))
    return canbe_se

"""

if __name__ == "__main__":
    path = "../../tests/testdata/ramp_5HPs_mix.trk"
    track = Track(path = path)
    mod = RampModel()
    ramp = RampControler.FromTrack(track,model = mod)    
    print(ramp.beads)
