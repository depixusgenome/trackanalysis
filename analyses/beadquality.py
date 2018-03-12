#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import pandas               as pd
import numpy                as np
from matplotlib.ticker import MultipleLocator
import matplotlib.pyplot    as plt
import holoviews            as hv
import seaborn              as sns
from math import pi

from bokeh.io import show
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    LinearColorMapper,
    BasicTicker,
    PrintfTickFormatter,
    ColorBar,
)
from bokeh.plotting import figure

import sankey



def resumeTracksQuality(tracks):
    """
    (DictTracks/Track) -> pandas dataframe
     Input: DictTracks or Tracks object. 
     Output: a dataframe with the summary of good, bad, missing and total number of beads
    The output dataframe has the track (or tracks) as index and 4 columns indicating good, bad, missing and total number of beads
    Example:
    >>> resumeTracksQuality(tracks)
    """
    #identify if we have a single track or dict tracks
    try:
        tracks.keys()
        is_dict = True
    except AttributeError:
        is_dict = False 
    #loop to fill the list with the results for single or dict tracks
    results = list()                            
    if is_dict:
        for key,val in tracks.items():
            #print(key,set(tracks.availablebeads())-set(val.beads.keys()))
            #print('good',list(val.cleaning.good()))
            #print('bad',list(val.cleaning.bad()))
            missing = len(set(tracks.availablebeads())-set(val.beads.keys()) ) 

            #print(missing)
            tot = len(list(tracks.availablebeads()) )#len(list(val.beadsonly.keys()))
            good = len(list(val.cleaning.good()))
            bad = len(list(val.cleaning.bad()))
            results.append({'Track': key,
                            'Total': tot,
                            'Good': good,
                            'Bad': bad,
                            'Missing':missing})
        results = pd.DataFrame(results,columns=['Track',
                                                'Good',
                                                'Bad',
                                                'Missing',
                                                'Total'])
        results.set_index('Track',inplace=True)
    else:
        results.append({'Track': tracks.key,
                        'Total' : len(list(tracks.beadsonly.keys())),
                        'Good' : len(list(tracks.cleaning.good())),
                        'Bad':  len(list(tracks.cleaning.bad())) })
        results = pd.DataFrame(results,columns=['Track',
                                                'Good',
                                                'Bad',
                                                'Total'])
        results.set_index('Track',inplace=True)
    return results


def dfGoodBadBeads(tracks):
    """
    (DictTracks/Track,list) -> pandas dataframe
    Input: Track or DictTracks object
    Output: Dataframe with the quality of the bead. The cell [bd,trk] is 0 if the bead bd is bad in track trk. The value of the cell is 1 if the bead is good.
     Example:
     dfGoodBadBeads(tracks)
     """
    try:
        tracks.keys()
        is_dict=True
    except AttributeError:
        is_dict = False
    
    if is_dict:
        all_beads = tracks.availablebeads()
    else:
        all_beads = list(tracks.beadsonly.keys())    
    
    df_good_bad = {}
    df_good_bad['bead'] = all_beads

    if is_dict:
        for trk,val in tracks.items():
            clean_beads = val.cleaning.good()
            df_good_bad[trk] = list(map(lambda x: x in clean_beads and 1 or 0,all_beads))
    else:
        clean_beads = tracks.cleaning.good()
        df_good_bad[tracks.key] = list(map(lambda x: x in clean_beads and 1 or 0,all_beads))

    df_good_bad = pd.DataFrame(df_good_bad)

    #order by the best beads. A bead is better than another if it is 'good' in more tracks
    tmp = df_good_bad.loc[:, df_good_bad.columns != 'bead']
    idx = tmp.sum(axis=1).sort_values(ascending=True).index #order by sum of good beads by track
    cols = df_good_bad.loc[idx].sum().sort_values(ascending=False).index #order by sum of good tracks per bead
    df_good_bad = df_good_bad.loc[idx]
    df_good_bad = df_good_bad[cols]
    return df_good_bad

def ismissing(bead,tracks,track_name):
    """
    (int,Dict Track,str)-> bool
    Input: bead is the label of the bead, tracks is a Dict Track object, track_name is a string contanining the name of the track
    Output: True if bead is missing in track, False otherwise
    Example:
    if 'GTC' belongs to tracks, we want to test if the bead 1 is missing or not from track GTC
    >>>(1,tracks,'GTC')
    True
    """
    return bead in set(tracks.availablebeads())-set(tracks[track_name].beads.keys())

#Auxiliary function resumeBeadsQuality: outputs a dataframe with the # of errors for each bead, for each type of error
def resumeBeadsQuality(tracks,ordertracks=None):
    """
    (DictTracks or single Track,list of str) -> pandas dataframe
    Input: DictTracks or Track object and a list of the order of tracks (only necessary for DictTrack) 
    Output: dataframe of frequence of errors per bead per track. The line bd/trk has 5 corresponding columns representing the 5 types of errors that can be detected for a bead. If the bead is missing all errors are set to NaN 
    Example:
    resumeBeadsQuality(track)
    resumeBeadsQuality(tracks,order_tracks_chrono)
    """
    try:
        tracks.keys()
        is_dict=True
    except AttributeError:
        is_dict = False
 
    dfmsg = tracks.cleaning.messages()
    dfmsg = dfmsg.reset_index()
    if is_dict:
        all_beads = tracks.availablebeads()
    else:
        all_beads = list(tracks.beadsonly.keys())
                                                             #Create a dataframe with rows = key and columns = possible errors. 
#The cells contain the nb of cycles in track that present the corresponding error
#The columns are :  [track extent population hfsigma< hfsigma> saturation]
    dict_msg = {'bead':1,'track':'','extent<0.5':0,'hfsigma<0.0001':0, 'hfsigma>0.01':0,'pop<80%':0,'sat>90%':0}
    msg = [dict_msg]
    if is_dict:
        for bd in all_beads:   
            tmp = dfmsg[dfmsg['bead']==bd]
            for tr in ordertracks:
                #check if bd is missing in tr and set values to None
                if ismissing(bd,tracks,tr):
                    dict_aux = {'bead': bd,
                                'track': tr,
                                'extent<0.5': None,
                                'hfsigma<0.0001': None,
                                'hfsigma>0.01': None,
                                'pop<80%': None,
                                'sat>90%': None}
                else:
                 #fill the dictionary of results for the non missing beads
                    dict_aux = {'bead':bd,
                                'track':tr,
                                'extent<0.5':0 if tmp[(tmp['key']==tr) & (tmp['message']== '< 0.50' )]['cycles'].empty else tmp[(tmp['key']==tr) & (tmp['message']== '< 0.50' )]['cycles'].values[0] ,
                                'hfsigma<0.0001':0 if tmp[(tmp['key']==tr) & (tmp['message']== '< 0.0001' )]['cycles'].empty else tmp[(tmp['key']==tr) & (tmp['message']== '< 0.0001' )]['cycles'].values[0] ,
                                'hfsigma>0.01':0 if tmp[(tmp['key']==tr) & (tmp['message']== '> 0.0100' )]['cycles'].empty else tmp[(tmp['key']==tr) & (tmp['message']== '> 0.0100' )]['cycles'].values[0] ,
                                'pop<80%':0 if tmp[(tmp['key']==tr) & (tmp['message']== '< 80%' )]['cycles'].empty else tmp[(tmp['key']==tr) & (tmp['message']== '< 80%' )]['cycles'].values[0] ,
                                'sat>90%':0 if tmp[(tmp['key']==tr) & (tmp['message']== '> 90%' )]['cycles'].empty else tmp[(tmp['key']==tr) & (tmp['message']== '> 90%' )]['cycles'].values[0] }
                msg.append(dict_aux)
    else:
        for bd in all_beads:   
            tmp = dfmsg[dfmsg['bead']==bd]
            dict_aux = {'bead':bd,
                        'track':tracks.key,
                        'extent<0.5':0 if tmp[ (tmp['message']== '< 0.50' )]['cycles'].empty else tmp[ (tmp['message']== '< 0.50' )]['cycles'].values[0] ,
                                                                                     'hfsigma<0.0001':0 if tmp[ (tmp['message']== '< 0.0001' )]['cycles'].empty else tmp[ (tmp['message']== '< 0.0001' )]['cycles'].values[0] ,
                        'hfsigma>0.01':0 if tmp[(tmp['message']== '> 0.0100' )]['cycles'].empty else tmp[ (tmp['message']== '> 0.0100' )]['cycles'].values[0] ,
                        'pop<80%':0 if tmp[(tmp['message']== '< 80%' )]['cycles'].empty else tmp[ (tmp['message']== '< 80%' )]['cycles'].values[0] ,
                                                                                     'sat>90%':0 if tmp[(tmp['message']== '> 90%' )]['cycles'].empty else tmp[ (tmp['message']== '> 90%' )]['cycles'].values[0] }
            msg.append(dict_aux)
    del msg[0]
    return pd.DataFrame(msg)#[list(dict_msg.keys())]


#Auxiliary function TypeError: outputs a dataframe columns are the tracks rows the beads,
#each cell contains the status of the bead: noError, extent>0.5,...
def typeError(df_resumeBeadsQuality,orderbeads,ordertracks):
    """
    (output from resumeBeadsQuality,list of int,list of str) -> pandas df
    Input:  output from resumeBeadsQuality,list of beads order,list of tracks order
    Output: dataframe of status of bead per track. The cell [bd,trk] is 0 contains the name of the most common error for bd in trk.
    Example:
    typeError(df_resumeBeadsQuality_single,order_beads_normal_single,order_tracks_chrono_single)
    """ 
    df_resumeBeadsQuality = df_resumeBeadsQuality.assign(mostCommonError =df_resumeBeadsQuality.set_index(['bead','track']).idxmax(axis=1).values)
    df_resumeBeadsQuality = df_resumeBeadsQuality.assign(mostCommonError = np.where(df_resumeBeadsQuality.set_index(['bead','track']).max(axis=1)==0,
'noError',
df_resumeBeadsQuality['mostCommonError']))
    df_resumeBeadsQuality = df_resumeBeadsQuality[['bead','track', 'mostCommonError']]

    aux = pd.DataFrame('', index=orderbeads, columns=ordertracks)

    for bd in df_resumeBeadsQuality['bead'].unique():
        for trk in df_resumeBeadsQuality['track'].unique():
            aux.loc[bd][trk] = df_resumeBeadsQuality[(df_resumeBeadsQuality['bead']==bd) & (df_resumeBeadsQuality['track']==trk)].mostCommonError.values[0]

    return aux
   

#Function barBeadsByType that outputs a stacked bar chart (pandas) with percentage beads by their status
def barBeadsByType(df_typeerror_single,ordertracks):
    """
    (output of typeError,list of str)-> pandas stacked bar chart
    Input: output from typeError for a single track, list of tracks order
    Output: stacked bar chart with the percentage of beads by their status
    Example: barBeadsByType(df_typeError_single,order_tracks_chrono_single)
    """

    data_counts = df_typeerror_single[ordertracks[0]].value_counts()

    dict_msg = {'noError':0, 'extent<0.5':0, 'hfsigma<0.0001':0, 'hfsigma>0.01':0, 'pop<80%':0, 'sat>90%':0}
    msg = [dict_msg]
    dict_aux = {'noError':0 if ('noError' in set(dict_msg.keys()).difference(data_counts.index) ) else data_counts.loc[['noError']].values[0] ,
                'extent<0.5':0 if ('extent<0.5' in set(dict_msg.keys()).difference(data_counts.index) ) else data_counts.loc[['extent<0.5']].values[0],
                'hfsigma<0.0001':0 if ('hfsigma<0.0001' in set(dict_msg.keys()).difference(data_counts.index) ) else data_counts.loc[['hfsigma<0.0001']].values[0] ,
                'hfsigma>0.01':0 if ('hfsigma>0.01' in set(dict_msg.keys()).difference(data_counts.index) ) else data_counts.loc[['hfsigma>0.01']].values[0] ,
                'pop<80%':0 if ('pop<80%' in set(dict_msg.keys()).difference(data_counts.index) )  else data_counts.loc[['pop<80%']].values[0] ,
                'sat>90%':0 if ('hfsigma<0.0001' in set(dict_msg.keys()).difference(data_counts.index) ) else data_counts.loc[['sat>90%']].values[0]
                }
    msg.append(dict_aux)
    del msg[0]
    msg = list(msg)
    msg = pd.DataFrame(msg)
    msg = msg[['noError','extent<0.5','hfsigma<0.0001', 'hfsigma>0.01','pop<80%','sat>90%']]
    msg.index = ordertracks
    mycolors = [ "#006400","#B22222","#8B008B","#C71585", "#FF4500","#FF7F50"]
    ax = pd.DataFrame(msg.transpose()).transpose().plot(kind='barh',
                                                        stacked=True,
                                                        color = mycolors)
    # create a list to collect the plt.patches data
    totals = []

    # find the values and append to list
    for i in ax.patches:
        totals.append(i.get_width())
        totals = [t for t in totals if t!=0]
        total = sum(totals)

    # set individual bar lables using above list
    acc = 0
    counter = 0
    yshift = [-0.03, 0.55, -0.03, 0.55, -0.03, 0.55]
    for i in ax.patches:
        if  i.get_width()!=0:
            # get_width pulls left or right; get_y pushes up or down
            x = acc + i.get_width()/2
            ax.text(x-1.8, i.get_y()+yshift[counter], \
                str(round((i.get_width()/total)*100, 1))+'%', fontsize=15,
                color=mycolors[counter])
            acc = acc + i.get_width()
        counter = counter+1

    ax.invert_yaxis()
    plt.xlabel('Nb of beads',fontsize=15)
    mylegend = plt.legend()
    mylegend.get_texts()[0].set_text('No Error')
    mylegend.get_texts()[1].set_text(r'$\Delta z$ too small')
    mylegend.get_texts()[2].set_text(r'$\sigma[HF]$ too low')
    mylegend.get_texts()[3].set_text(r'$\sigma[HF]$ too high')
    mylegend.get_texts()[4].set_text(r'not enough points/cycles')
    mylegend.get_texts()[5].set_text(r'non-closing')
    ax.figure.set_size_inches(20,15)
    ax.set_axisbelow(True)
    ax.yaxis.grid(which="major", color='black', linestyle='-', linewidth=0)
    ml = MultipleLocator(10)
    ax.xaxis.set_minor_locator(ml)
    ax.xaxis.grid(which='minor', color='black', linestyle='--', linewidth=0.8, alpha=0.3)
    rc={'font.size': 20, 'axes.labelsize': 15, 'legend.fontsize': 16, 
        'axes.titlesize': 20, 'xtick.labelsize': 15, 'ytick.labelsize': 20}
    plt.rcParams.update(**rc) 
    return ax

#Create a dataframe fit to holoviews with nested categories. Columns are [bead track typeOfError nbErrors]
#one row correspond to one beads, in one specific track, that has nbErrors of the specific typeOfError
def dfCleaningMessages(tracks,orderbeads,ordertracks=None):
    """
    (tracks,list,list) -> pandas df
    Input: track or DictTrack, list of beads order, list of tracks order
    Output: pandas df with columns Index, NbErrors, bead, track, typeOfError.
    Create a dataframe for holoviews with nested categories. One row correspond to one bead, in one specific track that has nbErrors of the specific typeOfError.
    Example: 
    dfCleaningMessages(track,order_beads_normal_single)
    dfCleaningMessages(tracks,order_beads_normal,order_tracks_chrono)
    """
    try:
        tracks.keys()
        is_dict=True
    except AttributeError:
        is_dict = False

    dfmsg = tracks.cleaning.messages()

    #replace labels and names of columns
    dfmsg_reset = dfmsg.reset_index()
    dfmsg_reset = dfmsg_reset[['bead','key','message','cycles']] # ,'types','bead'
    dfmsg_reset.rename(columns={"bead":"bead","key": "track", "message": "typeOfError", "cycles":"NbErrors"},inplace=True)
    dfmsg_reset.replace('< 0.50','extent<0.5',inplace=True)
    dfmsg_reset.replace('< 80%' ,'pop<80%',inplace=True)
    dfmsg_reset.replace('< 0.0001','hfsigma<0.0001',inplace=True)
    dfmsg_reset.replace('> 0.0100','hfsigma>0.01',inplace=True)
    dfmsg_reset.replace('> 90%','sat>90%',inplace=True)

#### COMPLETE THE DF WITH 0's WHERE THERE IS NO INFORMATION ################
###HOW TO ADD ONE ROW TO DATAFRAME
#df_test = pd.DataFrame([{'bead':0,'track':'GAG','typeOfError':'pop<80%','NbErrors':0}])
#dfmsg_reset = dfmsg_reset.append(df_test)

    alltypes = {'extent<0.5','pop<80%','hfsigma<0.0001','hfsigma>0.01','sat>90%'}
    if is_dict:
        for bead in orderbeads:
            for trk in ordertracks:
                presenttypes = set(dfmsg_reset[(dfmsg_reset['bead']==int(bead)) & (dfmsg_reset['track']==trk)]['typeOfError'])
                missingtypes = alltypes - presenttypes
                if len(missingtypes)>0:
                    for adderror in missingtypes:
                        df_test = pd.DataFrame([{'bead':int(bead),'track':str(trk),'typeOfError':adderror,'NbErrors':0}])
                        dfmsg_reset = dfmsg_reset.append(df_test)
    else:
        for bead in orderbeads:
            presenttypes = set(dfmsg_reset[(dfmsg_reset['bead']==int(bead))]['typeOfError'])
            missingtypes = alltypes - presenttypes
            if len(missingtypes)>0:
                for adderror in missingtypes:
                    df_test = pd.DataFrame([{'bead':int(bead),'track':tracks.key,'typeOfError':adderror,'NbErrors':0}])
                    dfmsg_reset = dfmsg_reset.append(df_test)

    dfmsg_reset = dfmsg_reset.reset_index()

    if is_dict:
        #to sort from best to worst track
        dfmsg_reset.track = dfmsg_reset.track.astype("category")
        dfmsg_reset.track = dfmsg_reset.track.cat.set_categories(ordertracks,ordered=True)
        dfmsg_reset.sort_values(by='track',inplace=True) 

    #dfmsg_reset.sort_values(by=['bead'])[dfmsg_reset.sort_values(by=['bead'])['bead']==40].sort_values(by='track')
    return dfmsg_reset


#Function barBeads that outputs a bar chart per bead, with columns tracks where the
#y-axis represents the number of errors (per type of error) for that bead 
#in the specific track
def barBeads(tracks,df_dfGoodBadBeads,dfmsg,ordertracks,orderbeads):
    """
    (tracks,output dfGoodBadBeads,output dfCleaningMessages,list,list) -> holoviews bar chart
    Input: track or DictTrack, output of dfGoodBadBeads, output of dfCleaningMessages, list of tracks order, list of beads order
    Output: holoviews bar chart per bead. The y-axis represents the number of errors (per type of error) for that bead in the corresponding track
    Example: 
    barBeads(track,df_dfGoodBadBeads_single,dfmsg_single,order_tracks_chrono_single,order_beads_normal_single)
    """
    try:
        tracks.keys()
        is_dict=True
    except AttributeError:
        is_dict = False

    #%%output size = 300
    #%%opts Bars [category_index=2 stack_index=0 group_index=1 legend_position='top' legend_cols=7 color_by=['stack'] tools=['hover']] 
    ###%%opts Bars.Stacked [stack_index='typeOfError'  ]  
    ### %%opts Bars.Grouped [group_index='typeOfError'  ] 
    ### %%opts Bars.Stacked (color=Cycle(values=["#B22222","#8B008B","#C71585", "#FF4500","#FF7F50"]))
    #    %%
    #%%opts Bars (color=Cycle(values=["#B22222","#8B008B","#C71585", "#FF4500","#FF7F50"]))

    #%%opts Bars.Stacked (color=Cycle(values=["#B22222","#8B008B","#C71585", "#FF4500","#FF7F50"]))

    ordertracks = np.asarray(ordertracks)
    orderbeads = np.asarray(orderbeads)
    #orderbeads = list(orderbeads.astype(str))
    #title_format="tt"+badbead]
    ### HOLOVIEWS STACKED BAR ###
    # http://holoviews.org/reference/elements/bokeh/Bars.html

    #data_pc = df_dfGoodBadBeads[np.insert(ordertracks,0,'bead')]
    data_pc = df_dfGoodBadBeads.set_index('bead')
    goodpc = data_pc.astype('float').sum(axis=1)
    goodpc = goodpc.astype('float')
    N = len(ordertracks)

    def holo_bars(bead):
        copy = dfmsg
        copy = copy[copy['bead']==bead]
        copy = copy[['track','typeOfError','NbErrors']] 
        if is_dict:
            copy = copy.sort_values(['track','typeOfError'])
            #trackcount = N-goodpc.loc['{:.0f}'.format(bead)])
            #mytitle = ("Bad Bead in {trackcount:.0f} out of {alltracks:.0f} ({pc:.1f} %)"
             #           .format(trackcount = N-goodpc.loc['{:.0f}'.format(bead)],
             #                   alltracks = N,
             #                   pc = (N-goodpc.loc['{:.0f}'.format(bead)])/N*100)
             #           )

            #mytitle= 'Bad Bead in '+ '{:.0f}'.format(N-goodpc.loc['{:.0f}'.format(bead)]) + ' out of '+ str(N) + '{:.0f}'.format(goodpc.loc['{:.0f}'.format(bead)]) #
            #mytitle ='Bad Bead in '+'{:.0f}'.format((N-goodpc.loc[bead]))+' out of '+str(N)+' tracks ('+str(round((N-goodpc.loc[bead])/N*100,1))+'%) -' 
            ##### to debug####  'nada '+ '{:.0f}'.format((N-goodpc.loc[bead])) # '{:.0f}'.format(N-goodpc.loc['{:.0f}'.format(bead)])#
        else:
            copy = copy.sort_values(['track','typeOfError'])
            mytitle= 'Bad bead -' if N-goodpc.loc[bead]!=0 else 'Good Bead -'
        if not is_dict:
            copytable = hv.Table(copy)
            barplot = copytable.to.bars(['typeOfError', 'track'], 'NbErrors', [],label=mytitle).redim.range(NbErrors=(0,200))
            #barplot = hv.Bars(copy,  ['track','typeOfError'], ['NbErrors'],group='Grouped',label=mytitle).redim.range(NbErrors=(0, 600)) #,group='Stacked'
            #barplot.relabel(group='Stacked')
        else:
            barplot = hv.Bars(copy,  ['track','typeOfError'], ['NbErrors'],group='Stacked').redim.range(NbErrors=(0, 600)) #,group='Stacked'

        axes_opts = {'xrotation': 45}
        return barplot.opts(plot=axes_opts)#.relabel(group='Grouped')#*hv.Text(0, 400, 'Quadratic Curve')
        #return barplot

    dmap = hv.DynamicMap(holo_bars, kdims=['bead'])
    # dmap.redim.values(badbead = sorted(tracks.availablebeads())) #normal sort

    #TO DEBUG
    #hvbar_single = barBeads(track,df_dfGoodBadBeads[['bead','AGC']],dfmsg[dfmsg.track=='AGC'],order_tracks_chrono_single,order_beads_normal_single)
    #hvbar_single
    mybeads = [float(i) for i in orderbeads]
    return dmap.redim.values(bead = mybeads).redim(NbErrors = "Count")


#Function heatmapBeadsByStatus that outputs seaborn heatmap with the number of good beads per track, and bad goods by type of error
def heatmapBeadsByStatus(df_resumeBeadsQuality,ordertracks,pc=True, order = 'chrono'):
    """
    (output resumeBeadsQuality, list, bool, str) -> seaborn heatmap
    Input: df_resumeBeadsQuality is the output of the function resumeBeadsQuality, list of tracks order, percentage True or False, order 'chrono' for chronological and 'best' for from best to worst
    Output: 2 seaborn heatmaps side to side. Columns are types of Error and rows are tracks. Each cell presents the percentage of appearance of the specific error at the specific track
    Example:
    heatmapBeadsByStatus(df_resumeBeadsQuality,order_tracks_chrono)
    """
    
    df_resumeBeadsQuality = df_resumeBeadsQuality[['bead','track',
                                        'extent<0.5','hfsigma<0.0001',
                                        'hfsigma>0.01','sat>90%','pop<80%']]
    df_resumeBeadsQuality = df_resumeBeadsQuality.assign(mostCommonError = df_resumeBeadsQuality.set_index(['bead','track']).idxmax(axis=1).values)
    df_resumeBeadsQuality = df_resumeBeadsQuality.assign(mostCommonError = np.where(df_resumeBeadsQuality.set_index(['bead','track']).max(axis=1)==0, 'noError', df_resumeBeadsQuality['mostCommonError']))
    df_resumeBeadsQuality['mostCommonError'] = df_resumeBeadsQuality['mostCommonError'].fillna('missing')
    if pc:
        data_discarded = pd.crosstab(df_resumeBeadsQuality['track'], 
                                     df_resumeBeadsQuality['mostCommonError'], normalize='index')*100
    else:
        data_discarded = pd.crosstab(df_resumeBeadsQuality['track'],
                                     df_resumeBeadsQuality['mostCommonError'])
    errors = ['extent<0.5','hfsigma<0.0001','hfsigma>0.01','sat>90%','pop<80%','missing','noError']
    data_discarded = data_discarded.reindex(columns = errors,
                                                       fill_value=0)
    
    data_discarded = data_discarded.loc[ordertracks]
 #   data_discarded = data_discarded.sort_values(['noError'],ascending=False)

    fig, ax =plt.subplots(ncols=2)
    fig.set_size_inches(16, 18)
    myfmt = '.1f' if pc else '.0f'
    prefix_title = '%' if pc else '#'
    noError_beads = sns.heatmap(data_discarded[['noError']],
                                annot=True,
                                fmt=myfmt,
                                cmap='Greens',
                                vmin = 0,
                                vmax = 100,
                                linewidths=0.5,
                                ax=ax[0],
                                square=True)
    noError_beads.set_yticklabels(noError_beads.get_yticklabels(),rotation=0)
    noError_beads.set_xticklabels(['No Error'])
    noError_beads.set_xticklabels(noError_beads.get_xticklabels(),rotation=30)
    total_beads = len(df_resumeBeadsQuality['bead'].unique())
    ax[0].set_title(prefix_title+' of Beads Status = No Error (Total {:.0f} beads)'.format(total_beads))
    ax[0].set_xlabel('')
    ax[0].set_ylabel('Tracks ('+['chronological' if order=='chrono' else 'best-to-worst'][0]+' order top-to-bottom)')
    data_discarded.pop('noError')
    error_beads = sns.heatmap(data_discarded,
                                annot=True,
                                fmt=myfmt,
                                vmin = 0,
                                vmax = 100,
                                cmap='Reds',
                                linewidths=0.5,
                                ax=ax[1])
    error_beads.set_xticklabels(error_beads.get_xticklabels(),rotation=30)
    error_beads.set_xticklabels([r'$\Delta z$ too small',
                                r'$\sigma[HF]$ too low',
                                r'$\sigma[HF]$ too high',
                                r'not enough points/cycles',
                                r'non-closing',
                                r'missing'])
    error_beads.set_xticks([0,1,2,2.7,4.2,5.2])
    error_beads.set_yticklabels(error_beads.get_yticklabels(),rotation=0)

    ax[1].set_title(prefix_title+' of Beads by Status (Total {:.0f} beads)'.format(total_beads))
    ax[1].set_xlabel('')
    ax[1].set_ylabel('Tracks ('+['chronological' if order=='chrono' else 'best-to-worst'][0]+' order top-to-bottom)')
    plt.tight_layout()
    return ax


#Function heatmapGoodBad that outputs bokeh heatmap with the status the beads per track (Good or Bad beads)
def heatmapGoodBad(df_dfGoodBadBeads,ordertracks):
    """
    (output dfGoodBadBeads, list) -> bokeh heatmap
    Input: df_resumeBeadsQuality is the output of the function resumeBeadsQuality, list of tracks order, percentage True or False, order 'chrono' for chronological and 'best' for from best to worst
    Output: bokeh heatmap with the quality of the beads per track 
    Example:
    heatmapBeadsByType(df_resumeBeadsQuality,order_tracks_chrono)
    """
    df_dfGoodBadBeads['bead'] = df_dfGoodBadBeads['bead'].astype(str)
    df_dfGoodBadBeads = df_dfGoodBadBeads.set_index('bead')
    df_dfGoodBadBeads.columns.name = 'track'
    df_dfGoodBadBeads=df_dfGoodBadBeads.transpose()

    plotbeads = list(df_dfGoodBadBeads.columns)
    plottracks = ordertracks #list(df_dfGoodBadBeads.index) #this is order_tracks_chrono if we used that as the order before, otherwise it is best to worst

    # reshape to 1D array 
    df = pd.DataFrame(df_dfGoodBadBeads.stack(), columns=['quality']).reset_index()

    # colormap
    colors = [ "#8B0000","#006400"] #[ "#550b1d","#75968f"] #
    mapper = LinearColorMapper(palette=colors,  low=df.quality.min(), high=df.quality.max())
    source = ColumnDataSource(df)

    TOOLS = "hover,save,pan,box_zoom,reset,wheel_zoom"

    p = figure(title="Bead quality",
                x_range=plottracks,
                y_range=plotbeads,
                x_axis_location="above",
                plot_width=1000,
                plot_height=1500,
                tools=TOOLS,
                toolbar_location='below')
    p.grid.grid_line_color = None
    p.axis.axis_line_color = None
    p.axis.major_tick_line_color = None
    p.axis.major_label_text_font_size = "10pt"
    p.axis.major_label_standoff = 5
    p.axis.axis_label_standoff = 10
    p.xaxis.major_label_orientation = pi / 3

    p.rect(x="track", y="bead", width=1, height=1,
    source=source,
    fill_color={'field': 'quality', 'transform': mapper},
    line_color=None)

    color_bar = ColorBar(color_mapper=mapper,
                         major_label_text_font_size="9pt",
                         ticker=BasicTicker(desired_num_ticks=len(colors)),
                         formatter=PrintfTickFormatter(format="%s"),
                         label_standoff=10,
                         border_line_color=None,
                         location=(1, 0),
                         major_label_overrides={0:'Bad Beads',0.5:'',1:'Good Beads'},
                         major_tick_out=20)

    p.add_layout(color_bar, 'right')

    p.select_one(HoverTool).tooltips = [
    ('Bead/Track', '@bead @track'),
    ('Quality', '@quality'),
    ]
    return p


def heatmapGoodBadDetailed(df_state_beads,ordertracks,orderbeads):
    """
    (output resumeBeadsQuality, list,list) -> bokeh heatmap
    Input: df_resumeBeadsQuality is the output of the function resumeBeadsQuality, list of tracks order
    Output: bokeh heatmap with the status of the beads per track
    Example:
    heatmapGoodBadDetailed(df_resumeBeadsQuality,order_tracks_chrono,order_beads_best)
    """

    orderbeads = np.asarray(orderbeads)
    df_state_beads = df_state_beads.assign(mostCommonError =df_state_beads.set_index(['bead','track']).idxmax(axis=1).values)
    df_state_beads = df_state_beads.assign(mostCommonError = np.where(df_state_beads.set_index(['bead','track']).max(axis=1)==0,
                        'noError',
                        df_state_beads['mostCommonError']))
    df_state_beads = df_state_beads[['bead','track', 'mostCommonError']]

    plotbeads = orderbeads # df_state_beads['bead'].unique()
    plottracks = ordertracks # if order=='chrono' else order_tracks_best
    aux = pd.DataFrame('', index=plottracks, columns=plotbeads)

    for bd in plotbeads:
        for trk in plottracks:
            aux.loc[trk][bd] = df_state_beads[(df_state_beads['bead']==bd) & (df_state_beads['track']==trk)].mostCommonError.values[0]

    # reshape to 1D array 
    df = pd.DataFrame(aux.stack(), columns=['typeError']).reset_index()

    df['typeError'] = np.where(df['typeError']=='noError',int(0),df['typeError'])
    df['typeError'] = np.where(df['typeError']=='extent<0.5',int(1),df['typeError'])
    df['typeError'] = np.where(df['typeError']=='hfsigma<0.0001',int(2),df['typeError'])
    df['typeError'] = np.where(df['typeError']=='hfsigma>0.01',int(3),df['typeError'])
    df['typeError'] = np.where(df['typeError']=='pop<80%',int(4),df['typeError'])
    df['typeError'] = np.where(df['typeError']=='sat>90%',int(5),df['typeError'])

    df.columns = ['track','bead','typeError']
    df['typeError'] = df['typeError'].apply(pd.to_numeric,errors='coerce') 

# colormap
    colors = [ "#006400","#B22222","#8B008B","#C71585", "#FF4500","#FF7F50"] #

    mapper = LinearColorMapper(palette=colors, low=0,high=5) #low=df.typeError.min(), high=df.typeError.max())

    #source = ColumnDataSource(df)
    source=df
    df['bead'] = df['bead'].astype(str)

    TOOLS = "hover,save,pan,box_zoom,reset,wheel_zoom"

    plotbeads = plotbeads.astype(str) #change to string for the figure

    p = figure( plot_width=1000,
                plot_height=1500,
                title="Bead Status",
                x_range=plottracks,
                y_range=plotbeads,
                x_axis_location="above",
                tools=TOOLS,
                toolbar_location='below')

    p.grid.grid_line_color = None
    p.axis.axis_line_color = None
    p.axis.major_tick_line_color = None
    p.axis.major_label_text_font_size = "12pt"
    p.axis.major_label_standoff = 5
    p.axis.axis_label_standoff = 10
    p.xaxis.major_label_orientation = pi / 3

    p.rect(x="track", y="bead", width=1, height=1, source=df,
    fill_color={'field': 'typeError', 'transform': mapper},
    line_color=None)

    color_bar = ColorBar(color_mapper=mapper, major_label_text_font_size="13pt",
    ticker=BasicTicker(desired_num_ticks=len(colors)),
    formatter=PrintfTickFormatter(format="%s"),
    label_standoff=20, border_line_color=None, location=(1, 0),
    major_label_overrides={0:'noError',
                           1:'extent<0.5',
                           2:'hfsigma<0.0001',
                           3:'hfsigma>0.01',
                           4:'pop<80%',
                           5:'sat>90%'}, major_tick_out=20)

    p.add_layout(color_bar, 'right')

    p.select_one(HoverTool).tooltips = [
    ('Bead/Track', '@bead @track'),
    ('Type of Error', '@typeError'),
    ]
    return p


#Function flowBeads that outputs a flow diagram between two tracks showing the proportion
#of the beads classified by their status (their mostCommonError)
def flowBeads(df_sankey,first_track = None,last_track=None):
    #pd.options.display.max_rows=8
    #%matplotlib inline
#https://github.com/anazalea/pySankey
#test_sankey = aux.set_index('index')
    df_sankey = df_sankey.fillna('missing')
    if first_track==None:
        first_track = df_sankey.columns[0]
    if last_track==None:
        last_track = df_sankey.columns[-1]

    df_sankey = df_sankey[[first_track, last_track]]

#colors3 = [ "#006400","#B22222","#8B008B","#C71585", "#FF4500","#FF7F50"] #

    colorDict =  {'noError':'#006400',
                  'extent<0.5':'#B22222',
                  'hfsigma<0.0001':'#8B008B',
                  'hfsigma>0.01':'#C71585',
                  'sat>90%':'#FF4500', 
                  'pop<80%':'#FF7F50', 
                  'missing':'#00BFFF'}

    df_sankey.reset_index()
    df_sankey = df_sankey.reset_index()[[first_track,last_track]]
    df_sankey
    sankey.sankey(df_sankey[first_track],df_sankey[last_track],
                  aspect=20,
                  colorDict=colorDict,
                  fontsize=12,
                  leftLabels=['pop<80%',
                              'sat>90%',
                              'hfsigma>0.01',
                              'hfsigma<0.0001',
                              'extent<0.5',
                              'missing',
                              'noError'],
                  rightLabels=['pop<80%',
                               'sat>90%',
                               'hfsigma>0.01',
                               'hfsigma<0.0001',
                               'extent<0.5',
                               'missing',
                               'noError'])
    plt.gcf().set_size_inches(12,12)
    plt.title('Track '+first_track+ r'$\longrightarrow$ Track '+last_track)
    #plt.savefig('sankey.png',bbox_inches='tight',dpi=150)
    return plt
