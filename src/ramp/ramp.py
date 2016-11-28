import pandas as pd
import numpy
import bokeh.plotting
from bokeh.io import output_notebook, show, push_notebook
from bokeh.models import *

BOKEHTOOLS = "crosshair,pan,wheel_zoom,box_zoom,reset,save,hover"

def isAttached(s:pd.Series,scale = 5.0)->bool:
    u'''
    use as
    check that there is at least one opening and one closing
    that an opening cannot occur after a closing.
    restricting on each cycle except (17, 8),(22, 10),(32, 6),(55, 5),(55, 2),(55, 8),(55, 1),(55, 3),(55, 4),(55, 11),(55, 0),(55, 12)
    may require the time scale of phase 3 to measure a gap between op and cl (could be provide by other function)
    '''

    ds = s.rename_axis(lambda x:x-1) -s.rename_axis(lambda x:x+1)

    det = detect_outliers(ds,scale = scale)
    # at least one opening and closing
    if not (any(ds[det]>0) and any(ds[det]<0)):
        return False

    # last index of positive detected ds
    lposid = ds[(ds>0)&det].last_valid_index()
    negids = ds[(ds<0)&det].index
    if any((negids-lposid)<0):
        return False
    
    return True

def quantile_criteria(ds,scale:int = 5):
    u''''''
    # quantile detection
    q1 = ds.quantile(0.25)
    q3 = ds.quantile(0.75)
    max_outlier = q3+scale*(q3-q1)
    min_outlier = q1-scale*(q3-q1)
    return (ds>max_outlier)|(ds<min_outlier)


def mad_criteria(ds):
    u'''
    Median absolute deviation
    '''
    mad = abs(ds["z"]-ds["z"].median()).median()
    return ds["z"]>mad
    
def detect_outliers(ds,scale:int = 5.0):
    u'''
    return boolean indices (True for detected points, False otherwise)
    '''
    bids = quantile_criteria(ds,scale)
    return bids

def estimate_zmag_open(df,dz,scale:int = 5.0):
    u'''
    may need to refine the estimation

    '''
    
    bcids = [k for k in dz.keys() if isinstance(k[0],int)]
    beads = list(set([i[0] for i in bcids]))
    ncycles = max([i[1] for i in bcids])+1
    zmag_op = pd.DataFrame(index = beads,columns = range(ncycles))
    det = detect_outliers(dz,scale = scale)
    peaks = (dz[det]>0)
    
    
    zmag_op = pd.DataFrame(index = beads,columns = range(ncycles))

    for k in bcids:
        zmag_op.loc[k[0],k[1]] = (df[("zmag",k[1])][peaks[k]]).median()
     
    
    return zmag_op


def estimate_zmag_fully_open(df,dz,scale:int = 5.0,reverse_time:bool = False)->pd.DataFrame:
    u'''
    alternative approach to estimate the zmag_open

    '''
    
    bcids = (k for k in dz.keys() if isinstance(k[0],int))
    beads = list({i[0] for i in bcids})
    ncycles = max(i[1] for i in bcids)+1
    zmag_op = pd.DataFrame(index = beads,columns = range(ncycles))
    det = detect_outliers(dz,scale = scale)
    ids = dz[dz[det]]
    for bcid in bcids:
             zmag_op.loc[bcid[0],bcid[1]] = df[("zmag",bcid[1])][ids[bcid]] if numpy.isfinite(ids[bcid]) else numpy.nan

    return zmag_op


def alt2_estimate_zmag_open(df,dz,scale:int = 5.0):
    u'''
    Second alternate estimation of zmag_open
    The goal is to better estimate the zmag_op
    need to add weight to each 
    '''
    
    bcids = [k for k in dz.keys() if isinstance(k[0],int)]
    beads = list(set([i[0] for i in bcids]))
    ncycles = max([i[1] for i in bcids])+1
    zmag_op = pd.DataFrame(index = beads,columns = range(ncycles))
    det = detect_outliers(dz,scale = scale)
    peaks = (dz[det]>0)
    
    
    zmag_op = pd.DataFrame(index = beads,columns = range(ncycles))

    for k in bcids:
        zmag_op.loc[k[0],k[1]] = (df[("zmag",k[1])][peaks[k]]).median()
     
    
    return zmag_op

def estimate_zmag_close(df,dz,scale:int = 5.0,reverse_time:bool = False):
    u'''
    need to check whether the estimation is fine enough
    scale's value can be lower here than for estimate_zmag_open 
    '''
    bcids = [k for k in dz.keys() if isinstance(k[0],int)]
    beads = list(set([i[0] for i in bcids]))
    
    ncycles = max([i[1] for i in bcids])+1

    det = detect_outliers(dz,scale = scale)

    if reverse_time:
        ids = dz[dz[det]<0].apply(lambda x:x.last_valid_index())    
    else:
        ids = dz[dz[det]<0].apply(lambda x:x.first_valid_index())

    zmag_close = pd.DataFrame(index = beads,columns = range(ncycles))
    for bcid in bcids:
            zmag_close.loc[bcid[0],bcid[1]] = df[("zmag",bcid[1])][ids[bcid]] if numpy.isfinite(ids[bcid]) else numpy.nan
            
    return zmag_close

def sanitise_beads_collection(df,scale:int = 5.0,min_corr:float = 0.2,maxzmag_err:float = 0.01):
    u'''
    obsolete
    Implements a number of test performed on each bead and for each cycle.
    Should one bead fail a test at either cycle it is removed from the collection.
    
    Tests :
        *Can't use the zmax to estimate beads that don't open or not because of weird behaviour of some of the beads (see bead 0
        from /media/data/helicon/remi/2016-11-08/ramp_5HPs_mix.trk).
        *(1) The most reliable test found was to see if the bead "behaves" as expected, i.e. if there is some values of dz detected
        by function detect.
        *(2) z and zmag should be (more or less) correlated (corr>min_corr)
        *(3) estimation of zmag_op should be fine enough

    '''
    # first test on detection of outliers
    dz = df.rename_axis(lambda x:x-1)-df.rename_axis(lambda x:x+1)
    dz = dz.reindex(df.index)

    keys = [k for k in df.keys() if isinstance(k[0],int)]
    
    det = detect_outliers(dz,scale = scale)
    to_del = [k[0] for k in keys if det[k].sum() =  = 0]
    print(to_del)
    # second test on the correlation between z and zmag
    corrs = df.corr()
    to_del+ = [k[0] for k in keys if corrs[("zmag",k[1])][k]<min_corr]
    to_del = set(to_del)
    
    for d in to_del:
        for k in df.keys():
            if k[0] =  = d:
                df.pop(k)
                dz.pop(k)

    # third test on zmag estimation
    zmag_op = estimate_zmag_open(df,dz,scale = scale)
    stds = zmag_op.std(axis = 1)
    print(stds)
    zmag_op = zmag_op[stds<maxzmag_err]
    print (zmag_op)
    df = df[[c for c in df.columns if not isinstance(c[0],int) or c[0] in zmag_op.index]]
    dz = dz[df.columns]  
    print("to keep", df.keys())
    return df,dz,zmag_op




def can_be_struture_event(dz,detected):
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

def find_attached_beads(df,scale = 5.0,min_corr = 0.2,maxzmag_err = 0.01):
    u'''
    uses the the sanitise_beads_collection and returns the indices of kept beads
    '''
    df = sanitise_beads_collection(df,scale = scale,min_corr = min_corr,maxzmag_err = maxzmag_err)[0]
    beadids = list(set([k[0] for k in df.keys() if isinstance(k[0],int)]))
    beadids.sort()
    return beadids

def find_fixed_beads(df):
    u'''
    TO IMPLEMENT
    '''
    
    return

def find_untracked_beads(df):
    u'''
    TO IMPLEMENT
    '''
    
    return


def plot_stillopen_at_zmag(df,dz,scale = 5.0):
    u'''
    
    '''
    fig = bokeh.plotting.figure(title = "ratio of beads still open as zmag decreases",y_axis_label = "% of open beads",x_axis_label = "zmag",tools = BOKEHTOOLS)

    zmag = list(set(df[[k for k in df.keys() if k[0] =  = "zmag"][0]].values.flatten()))
    zmag.sort()

    zmag_cl = estimate_zmag_close(df,dz,scale = scale,reverse_time = False)

    # need to deal with zmag_cl = numpy.nan
    ratio = [(zmag_cl<z).values.flatten().sum()/float(zmag_cl.size) for z in zmag]
    fig.circle(zmag,ratio)
    return fig


def plot_stillclosed_at_zmag(df,dz,scale = 5.0):
    u'''
    
    '''
    fig = bokeh.plotting.figure(title = "ratio of beads still closed as zmag increases",y_axis_label = "% of open beads",x_axis_label = "zmag",tools = BOKEHTOOLS)

    zmag = list(set(df[[k for k in df.keys() if k[0] =  = "zmag"][0]].values.flatten()))
    zmag.sort()

    zmag_op = estimate_zmag_fully_open(df,dz,scale = scale,reverse_time = False)

    ratio = [(zmag_op<z).values.flatten().sum()/float(zmag_op.size) for z in zmag]
    fig.circle(zmag,ratio)
    return fig




