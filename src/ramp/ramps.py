#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Interface between Jupyter and rampcore
"""
import numpy     as np
import holoviews as hv

from .rampcore import RampData , RampModel # pylint: disable=unused-import

# def plotzzmag(data:RampData):
#     "returns plot of Z function of Zmag"
#     zmags = estzmagclose(data)
#     goods = list(data.getgoodbeadids())
#     specs = {"Curve":{"style":dict(color="blue")},
#              "Spikes.allzmags":{"style":dict(color="black")},
#              "Spikes.curr":{"style":dict(color="red")}}
#     spks  = hv.Spikes(zmags[goods],label="allzmags")
#     def _getzzmagplot(beadid):
#         "plots for all cycles a single bead"
#         ids   = list(filter(lambda x:x[0]==beadid,data.bcids))
#         curve = hv.Curve([])
#         for i in ids:
#             curve *= hv.Curve(list(zip(data.dataz[("zmag",i[1])].values,data.dataz[i].values)))

#         #spk1 = hv.Curve([(zmags[beadid],0.0),(zmags[beadid],0.5)],label="curr")
#         spk1 = hv.Spikes([zmags[beadid]],label="curr")
#         layout = (curve+spks*spk1).cols(1)
#         layout.opts(specs)
#         return layout

#     asort= np.argsort(zmags[goods])
#     dmap = hv.DynamicMap(_getzzmagplot,kdims=["bid"]).redim.values(bid=np.array(goods)[asort])
#     dmap.opts(specs)
#     return dmap


def plotzzmag(data:RampData):
    "returns plot of Z function of Zmag"
    zmags = estzmagclose(data)
    goods = list(data.getgoodbeadids())
    specs = {"Curve":{"style":dict(color="blue")},
             "Spikes.allzmags":{"style":dict(color="black")},
             "Spikes.curr":{"style":dict(color="red")}}
    spks  = hv.Spikes(zmags[goods],label="allzmags")
    def _getzzmagplot(beadid):
        "plots for all cycles a single bead"
        ids   = list(filter(lambda x:x[0]==beadid,data.bcids))
        curve = hv.Curve([])
        for i in ids:
            curve *= hv.Curve(list(zip(data.dataz[("zmag",i[1])].values,data.dataz[i].values)))

        #spk1 = hv.Curve([(zmags[beadid],0.0),(zmags[beadid],0.5)],label="curr")
        spk1 = hv.Spikes([zmags[beadid]],label="curr")
        layout = (curve+spks*spk1).cols(1)
        layout.opts(specs)
        return layout

    asort= np.argsort(zmags[goods])
    dmap = hv.DynamicMap(_getzzmagplot,kdims=["bid"]).redim.values(bid=np.array(goods)[asort])
    dmap.opts(specs)
    return dmap

def histzmagclose(data:RampData,discarded=None,**kwa):
    """
    histogram of estimated Zmag closed (see estzmagclose doc) for all good beads
    args:
    * data, RampData
    * discarded, list of bead ids to discard (default None)
    * see np.histogram doc for keyword arguments like bins, range etc ...
    eg:
    histzmagclose(data) # defaults to 10 bins
    histzmagclose(data,bins=np.linspace(-0.6,-0.4,20)) # 19 bins between -0.6 and -0.4
    histzmagclose(data,bins=10,range=(-0.5,-0.4)) # 10 bin from -0.5, -0.4

    """
    goods = data.getgoodbeadids()
    if not discarded is None:
        goods-=set(discarded)
    zmags = estzmagclose(data)
    return hv.Histogram(np.histogram(zmags[list(goods)],**kwa))

def estzmagclose(data:RampData,discard=None):
    """
    estimated zmag closed for each bead.
    returns the zmag such that 95% of cycles are closed for this bead
    args :
    * data, RampData
    * discard, list of bead ids (default None)
    """
    zmags  = data.zmagclose(reverse_time=True).values
    est = np.percentile(zmags,5,interpolation="higher",axis=1)

    if discard is None:
        return est
    return [v for i,v in enumerate(est) if i not in discard]
