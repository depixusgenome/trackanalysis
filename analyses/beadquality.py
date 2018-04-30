#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import pandas               as pd
import numpy                as np

from collections            import namedtuple
#from matplotlib.ticker import MultipleLocator
import matplotlib.pyplot    as plt
import holoviews            as hv
import seaborn              as sns
from math import pi

#from bokeh.io import show
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    LinearColorMapper,
    BasicTicker,
    PrintfTickFormatter,
    ColorBar,
    FixedTicker,
    FuncTickFormatter,
    Plot,
    BasicTickFormatter,
    CategoricalTickFormatter
    )
from bokeh.plotting import figure, show

import sankey



def resume_tracks_quality(tracks, dfmsg):
    """
    (DictTracks/Track, pandas dataframe) -> pandas dataframe
    Input: DictTracks or Tracks object, tracks.dfmsg.reset_index()
    Output: 
        * status:   dataframe with the status of bead per track. Either missing, 
                    fixed or NaN of it is neither missing nor fixed
        * table:    dataframe with a resume of fixed, missing and not fixed/missing            
    Example:
    >>> resume_tracks_quality(tracks, dfmsg)
    """
    #compute the chronological order of the tracks
    order_tracks = pd.Series(list(tracks.dataframe()
                                  .set_index('key')
                                  .sort_values(by='modification')
                                  .index.values))
    #identify if we have a single track or dict tracks
    try:
        tracks.keys()
        is_dict = True
    except AttributeError:
        is_dict = False
    #loop to fill the list with the results
    #results = list()
    if is_dict:
        ncycles = [trk.ncycles for name, trk in tracks.items()]
        stats = {k:None for k in tracks.keys()}
        for name, val in stats.items():
            stats[name] = {'ncycles': tracks[name].ncycles}
        statsdf = pd.DataFrame(stats)
        dfmsg['trackorder'] = [list(order_tracks).index(key) for key in dfmsg['key']]
        dfmsg['pc_cycles'] = [cycles/statsdf[key]['ncycles']*100 for key, cycles
                              in dfmsg[['key', 'cycles']].itertuples(index=False)]
        dfstatus = pd.DataFrame(columns= order_tracks, index= tracks.availablebeads())
        
        #hfsigma too low
        dfmsg100hfsigma = dfmsg[(dfmsg['types']=='hfsigma') & (
                                        dfmsg['message'].str.find("<")!=-1)].query(
                                                'pc_cycles==100').sort_values(
                                                        by=['bead','trackorder'])
        beads100hfsigma = set(map(tuple, dfmsg100hfsigma.
                                  sort_values(by=['bead', 'trackorder']).
                                  groupby(['bead', 'trackorder']).
                                  count().
                                  reset_index()[['bead', 'trackorder']].values
                                 ))
        for pair in beads100hfsigma:
            dfstatus.iloc[pair[0], pair[1]] = 'hf--low'
        #hfsigma too high
        dfmsg100hfsigma_high = dfmsg[(dfmsg['types']=='hfsigma') & (
                                             dfmsg['message'].str.find(">")!=-1 )].query(
                                                     'pc_cycles==100').sort_values(
                                                             by=['bead','trackorder'])

        beads100hfsigma_high = set(map(tuple, dfmsg100hfsigma_high.
                                       sort_values(by=['bead', 'trackorder']).
                                       groupby(['bead', 'trackorder']).
                                       count().
                                       reset_index()[['bead', 'trackorder']].values
                                      ))
        for pair in beads100hfsigma_high:
            dfstatus.iloc[pair[0], pair[1]] = 'hf--high'
        #ping pong appears
        dfmsg10pingpong = dfmsg[(dfmsg['types']=='pingpong')].query(
                'pc_cycles>10').sort_values(by=['bead', 'trackorder'])
        beads10pingpong = set(map(tuple, dfmsg10pingpong.
                                  sort_values(by=['bead', 'trackorder']).
                                  groupby(['bead', 'trackorder']).
                                  count().
                                  reset_index()[['bead', 'trackorder']].values
                                 ))                          
        for pair in beads10pingpong:
            dfstatus.iloc[pair[0], pair[1]] = 'pingpong'
        #if there is a good track after missing tracks,
        #then the previous tracks are not missing
        for bead_status in dfstatus.iterrows():
            missing = False
            for trknb, state in enumerate(pd.isnull(bead_status[1])):
                if(not state):
                    missing = True
                if(state==True & missing==True):
                    dfstatus.iloc[bead_status[0], 0:trknb] = np.nan
                    missing = False
        #if extent is too small, the bead is fixed, not missing
        dfmsg90extent_low = dfmsg[(dfmsg['types']=='extent') & (
                                          dfmsg['message'].str.find("<")!=-1 )].query(
                                                  'pc_cycles>99').sort_values(
                                                          by=['bead','trackorder'])
        beads90extent_low = set(map(tuple, dfmsg90extent_low.
                                    sort_values(by=['bead', 'trackorder']).
                                    groupby(['bead', 'trackorder']).
                                    count().
                                    reset_index()[['bead', 'trackorder']].values
                                   ))
        for pair in beads90extent_low:
            dfstatus.iloc[pair[0], pair[1]] = 'fixed'
        #stats over the results
        dfstatusstats = dfstatus.replace(['hf--low',
                                          'hf--high',
                                          'pingpong'], 'missing')
        stats_resume = dfstatusstats.fillna('not_fixed/missing').apply(pd.value_counts)

        results = namedtuple('Results', ['table', 'status'])
        output = results(table=stats_resume.transpose(), status=dfstatusstats)
        return output
    ######################## FOR ONE TRACK, OBSOLETE ##########################
    #else:
    #    results.append({'Track': tracks.key,
    #                    'Total' : len(list(tracks.beadsonly.keys())),
    #                    'Good' : len(list(tracks.cleaning.good())),
    #                    'Bad':  len(list(tracks.cleaning.bad()))})
    #    results = pd.DataFrame(results, columns=['Track',
    #                                             'Good',
    #                                             'Bad',
    #                                             'Total'])
    #    results = results.set_index('Track')
    #return results
    ######################### END FOR ONE TRACK OBSOLETE #####################

def evolution_missing_fixed(stats_resume,tracks):
    """
    (pandas df,list) -> holoviews scatter/line plot
    Input: output from resume_tracks_quality.table, list of tracks
    Output: Scatter plot showing the evolution of the nb of missing, fixed and no-errors
    beads. 
    Example:
    >>> evolution_missing_fixed(resume.table,tracks)
    """
        
    stats_resume = stats_resume.transpose()
    valuesfixed = list(stats_resume.loc['fixed'])
    valuesmissing = list(stats_resume.loc['missing'])
    valuesok = list(stats_resume.loc['not_fixed/missing'])
    total = valuesfixed[0]+valuesmissing[0]+valuesok[0]

    dates = pd.DatetimeIndex(tracks.dataframe().sort_values(
        by='modification').modification.values)
    trkdates = ['d{0}-{1}h{2}m'.format(d.day,d.hour,d.minute) for d in dates]
        
    datafixed = [tup for tup in zip(trkdates,np.array(valuesfixed)/total*100)]
    datamissing = [tup for tup in zip(trkdates,np.array(valuesmissing)/total*100)]
    dataok = [tup for tup in zip(trkdates,np.array(valuesok)/total*100)]
    axes_opts={'xrotation': 45}

    return hv.Points(
        datafixed, label='fixed').redim.label(
            x='date', y='% beads (total {0})'.format(total)).redim.range(
                y=(0,100))*hv.Points(
                    datamissing, label='missing')*hv.Points(
                        dataok, label='ok')*hv.Curve(
                            datafixed, group='fixed')*hv.Curve(
                                datamissing, group='missing')*hv.Curve(
                                    dataok, group='ok', vdims=['nb']).opts(
                                            plot=axes_opts)

def ismissing(bead, track_name, dfstatus):
    """
    (int,str,pandas df)-> bool
    Input: bead is the label of the bead, tracks is a Dict Track object,
    track_name is a string contanining the name of the track
    Output: True if bead is missing in track, False otherwise
    Example:
    if 'GTC' belongs to tracks, we want to test if the bead 1 is missing
    or not from track GTC
    >>>ismissing(1,'GTC',dfstatus)
    True
    """
    return dfstatus[track_name][bead] == 'missing'

def isfixed(bead, track_name, dfstatus):
    """
    (int,str,pandas df)-> bool
    Input: bead is the label of the bead, tracks is a Dict Track object,
    track_name is a string contanining the name of the track
    Output: True if bead is fixed in track, False otherwise
    Example:
    if 'GTC' belongs to tracks, we want to test if the bead 1 is missing
    or not from track GTC
    >>>isfixed(1,'GTC',dfstatus)
    True
    """
    return dfstatus[track_name][bead] == 'fixed'

def resume_bead_quality(tracks, dfmsg, dfstatus, ordertracks=None):
    """
    (DictTracks or single Track,list of str) -> pandas dataframe
    Input: DictTracks or Track object and a list of the order of tracks
    (only necessary for DictTrack) 
    Output: 
        * res:  dataframe of frequence of errors per bead per track. 
                The line bd/trk has as many columns as the nb of types of 
                errors that can be detected for a bead. 
                If the bead is missing/fixed all errors are set to NaN 
        * detail : analogous to res, but missing and fixed are reported
    Example:
    resumeBeadsQuality(tracks, dfmsg, resume.status, order_tracks)
    """
    #check if the input is a single track or a dict of tracks
    try:
        tracks.keys()
        is_dict=True
    except AttributeError:
        is_dict = False
    
    #obtain all the messages from the cleaning process
    #dfmsg = tracks.cleaning.messages()
    #dfmsg = dfmsg.reset_index()

    #list of all available beads
    if is_dict:
        all_beads = tracks.availablebeads()
    else:
        all_beads = list(tracks.beadsonly.keys())

    #Create a dataframe with rows = key and columns = possible errors. 
    #The cells contain the nb of cycles in track that present 
    #the corresponding error
    #The columns are :  
    #[track extent population hfsigma< hfsigma> saturation]
    
    #extract the messages from dfmsg to create one dict per bead per track with all its error values
    df_unique_msg = dfmsg[['types','message']].values
    msg_unique = set(map(tuple,df_unique_msg))

    keys = []
    while len(msg_unique)!=0:
        elem = msg_unique.pop()
        keys.append(elem[0]+elem[1].replace(" ",""))

    dict_msg = {**{'bead':None,
                    'track':''},
                **dict.fromkeys(keys,None) } 

    #old dict_msg
    #dict_msg = {'bead':1,'track':'','extent<0.5':0,'hfsigma<0.0001':0, 'hfsigma>0.01':0,'pop<80%':0,'sat>90%':0}
    msg = [dict_msg]
    msg_missingfixed = [dict_msg]
    if is_dict:
        for bd in all_beads:
            tmp = dfmsg[dfmsg['bead']==bd]
            for tr in ordertracks:
                #check if bd is missing in tr and set values to None
                if (ismissing(bd, tr, dfstatus)) or (isfixed(bd, tr, dfstatus)): 
                    dict_aux = {**{'bead':bd,
                                   'track':tr},
                                **dict.fromkeys(keys,None) }
                    currentstatus = 'missing' if ismissing(bd,tr,dfstatus) else 'fixed'
                    dict_aux_missingfixed = {**{'bead': bd,
                                                  'track': tr},
                                              **dict.fromkeys(keys, currentstatus)}
                else:
                 #fill the dictionary of results for the non missing beads
                    for key_dict_msg, val_dict_msg in dict_msg.items():
                        if key_dict_msg == 'bead':
                            dict_aux = {key_dict_msg: bd}
                            dict_aux_missingfixed = {key_dict_msg: bd} 
                        elif key_dict_msg == 'track':
                            dict_aux[key_dict_msg] = tr
                            dict_aux_missingfixed[key_dict_msg] = tr
                        elif '<' in key_dict_msg:
                            dict_aux[key_dict_msg] = 0 if tmp[
                                (tmp['key'] == tr) &
                                (tmp['types'] == key_dict_msg.split('<')[0]) &
                                (tmp['message'] == '< '+key_dict_msg.split('<')[1])].empty else tmp[
                                    (tmp['key']==tr) &
                                    (tmp['types']==key_dict_msg.split('<')[0]) &
                                    (tmp['message']=='< '+key_dict_msg.split('<')[1])]['cycles'].values[0]
                            dict_aux_missingfixed[key_dict_msg] = dict_aux[
                                    key_dict_msg]
                        elif '>' in key_dict_msg:
                            dict_aux[key_dict_msg] = 0 if tmp[
                                (tmp['key']==tr) &
                                (tmp['types']==key_dict_msg.split('>')[0]) &
                                (tmp['message']=='> '+key_dict_msg.split('>')[1])].empty else tmp[
                                    (tmp['key']==tr) &
                                    (tmp['types']==key_dict_msg.split('>')[0]) &
                                    (tmp['message']=='> '+key_dict_msg.split('>')[1])]['cycles'].values[0]
                            dict_aux_missingfixed[key_dict_msg] = dict_aux[
                                    key_dict_msg]
                msg.append(dict_aux)
                msg_missingfixed.append(dict_aux_missingfixed)
    else:
        for bd in all_beads:   
        #### OBSOLETE revisit when updating the one track treatment ####
            tmp = dfmsg[dfmsg['bead']==bd]
            for key_dict_msg, val_dict_msg in dict_msg.items():
                if key_dict_msg == 'bead':
                    dict_aux = {key_dict_msg: bd}
                elif key_dict_msg == 'track':
                    dict_aux[key_dict_msg] = tracks.key
                elif '<' in key_dict_msg:
                    dict_aux[key_dict_msg] = 0 if tmp[(tmp['key']==tr) &
                                                     (tmp['types']==key_dict_msg.split('<')[0]) &
                                                     (tmp['message']=='< '+key_dict_msg.split('<')[1])].empty else tmp[(tmp['key']==tr) &
                                                                                             (tmp['types']==key_dict_msg.split('<')[0]) &
                                                                    (tmp['message']=='< '+key_dict_msg.split('<')[1])]['cycles'].values[0]
                elif '>' in key_dict_msg:
                    dict_aux[key_dict_msg] = 0 if tmp[(tmp['key']==tr) &
                                                     (tmp['types']==key_dict_msg.split('>')[0]) &
                                                     (tmp['message']=='> '+key_dict_msg.split('>')[1])].empty else tmp[(tmp['key']==tr) &
                                                                                             (tmp['types']==key_dict_msg.split('>')[0]) &
                                                                    (tmp['message']=='> '+key_dict_msg.split('>')[1])]['cycles'].values[0]
            msg.append(dict_aux)
    del msg[0]
    del msg_missingfixed[0]
    results = namedtuple('results', ['res', 'detail'])
    output = results(res=pd.DataFrame(msg), detail=pd.DataFrame(msg_missingfixed))
    return output

def order_bead_best(df_resumeBeadsQuality):
    """
    (output from resume_bead_quality) -> list of int 
    This function outputs the list of beads sorted by best to worst
    in terms of the errors the bead presents
    Example:
    order_bead_best(df_resumeBeadsQuality)
    """
    noerror_per_bead = df_resumeBeadsQuality.res.groupby(
                                                    'bead').count().iloc[:,1]
    noerror_per_bead = pd.DataFrame(noerror_per_bead)
    noerror_per_bead.columns = ['nb_noerrors']
    return noerror_per_bead.sort_values(
            by='nb_noerrors',ascending = False).reset_index().bead[::-1]


#Auxiliary function TypeError: outputs a dataframe columns are the tracks rows the beads,
#each cell contains the status of the bead: noError, extent>0.5,...
def typeError(df_resumeBeadsQuality,orderbeads,ordertracks):
    """
    (output from resumeBeadsQuality,list of int,list of str)->pandas df
    Input:  output from resumeBeadsQuality,list of beads order,list of tracks
    order
    Output: dataframe of status of bead per track. The status can be noError,
    fixed, missing, errors>=1
    Example:
    typeError(df_resumeBeadsQuality_single,
              order_beads_normal_single,
              order_tracks_chrono_single)
    """
    df = df_resumeBeadsQuality.detail.set_index(['bead','track'])
    df['missing'] = df.apply(
            lambda x: 1000000 if x[df.columns[0]] == 'missing' else 0, axis=1)
    df['fixed'] = df.apply(
            lambda x: 5000000 if x[df.columns[0]] == 'fixed' else 0, axis=1)

    df = df.replace('fixed', 5).replace('missing',1)
    df = df.astype('float', copy=False)

    df = df.assign(mostCommonError = df.idxmax(axis=1).values)
    df = df.assign(mostCommonError = np.where(
        df.max(axis=1) == 0,
        'noError',
        df.mostCommonError))
    df = df.assign(mostCommonError = np.where(
        (df.max(axis=1)>0) & (df.max(axis=1)<1000000),
        'errors>=1',
        df.mostCommonError))
    
    df = df.reset_index()[['bead','track', 'mostCommonError']]

    aux = pd.DataFrame('', index=orderbeads, columns=ordertracks)

    for bd in df['bead'].unique():
        for trk in df['track'].unique():
            aux.loc[bd][trk] = df[
                    (df['bead']==bd) & (df['track']==trk)].mostCommonError.values[0]
    return aux
   
#
#Function heatmapTracksStatus that outputs seaborn heatmap with the number
#of good beads per track, and bad goods by type of error
def heatmap_tracks_status(df_resumeBeadsQuality,ordertracks,pc=True, order = 'chrono'):
    """
    (output resumeBeadsQuality, list, bool, str) -> seaborn heatmap
    Input: df_resumeBeadsQuality is the output of the function resumeBeadsQuality,
    list of tracks order, percentage True or False, order 'chrono' for
    chronological and 'best' for from best to worst
    Output: 2 seaborn heatmaps side to side. Columns are types of Error and
    rows are tracks. Each cell presents the percentage of appearance of the
    specific error at the specific track
    Example:
    heatmapTracksStatus(df_resumeBeadsQuality,order_tracks_chrono)
    """
    #set first two columns bead and track
    df_resumeBeadsQuality = df_resumeBeadsQuality.set_index(
                                                         ['bead','track']).reset_index()
    df_resumeBeadsQuality = df_resumeBeadsQuality.assign(
                            mostCommonError = df_resumeBeadsQuality.set_index(
                                ['bead','track']).idxmax(axis=1).values)
    df_resumeBeadsQuality = df_resumeBeadsQuality.assign(
                            mostCommonError = np.where(
                                df_resumeBeadsQuality.set_index(
                                    ['bead','track']).max(axis=1)==0,
                                'noError', df_resumeBeadsQuality['mostCommonError']))
    df_resumeBeadsQuality['mostCommonError'] = df_resumeBeadsQuality[
            'mostCommonError'].fillna('missing/fixed')
    if pc:
        data_discarded = pd.crosstab(df_resumeBeadsQuality['track'], 
                                     df_resumeBeadsQuality[
                                         'mostCommonError'], normalize='index')*100
    else:
        data_discarded = pd.crosstab(df_resumeBeadsQuality['track'],
                                     df_resumeBeadsQuality['mostCommonError'])
    errors = list(df_resumeBeadsQuality.set_index(
        ['bead','track','mostCommonError']).columns) + ['missing/fixed','noError']
    outputtable = data_discarded.copy()
    data_discarded = data_discarded.reindex(columns = errors,
                                                       fill_value=0)
    
    data_discarded = data_discarded.loc[ordertracks]
    total_beads = len(df_resumeBeadsQuality['bead'].unique())
    fig, ax =plt.subplots(ncols=2)
    fig.set_size_inches(16, 18)
    myfmt = '.1f' if pc else '.0f'
    prefix_title = '%' if pc else '#'
    noError_beads = sns.heatmap(data_discarded[['noError']],
                                annot=True,
                                fmt=myfmt,
                                cmap='Blues',
                                vmin = 0,
                                vmax = 100 if pc else total_beads,
                                linewidths=0.5,
                                ax=ax[0],
                                square=True)
    noError_beads.set_yticklabels(noError_beads.get_yticklabels(),rotation=0)
    noError_beads.set_xticklabels(['No Error'])
    noError_beads.set_xticklabels(noError_beads.get_xticklabels(),rotation=30)
    ax[0].set_title(prefix_title+' of Beads Status = No Error (Total {:.0f} beads)'.format(total_beads))
    ax[0].set_xlabel('')
    ax[0].set_ylabel('Tracks ('+[
        'chronological' if order=='chrono' else 'best-to-worst'][0]+' order top-to-bottom)')
    data_discarded.pop('noError')
    error_beads = sns.heatmap(data_discarded,
                                annot=True,
                                fmt=myfmt,
                                vmin = 0,
                                vmax = 100 if pc else total_beads,
                                cmap='Reds',
                                linewidths=0.5,
                                ax=ax[1])
    error_beads.set_xticklabels(error_beads.get_xticklabels(),rotation=40)
    error_beads.set_yticklabels(error_beads.get_yticklabels(),rotation=0)

    ax[1].set_title(prefix_title+' of Beads by Status (Total {:.0f} beads)'.format(total_beads))
    ax[1].set_xlabel('')
    ax[1].set_ylabel('Tracks ('+[
        'chronological' if order=='chrono' else 'best-to-worst'][0]+' order top-to-bottom)')
    plt.tight_layout()
    from collections import namedtuple
    Results = namedtuple('Results', ['table','display'])
    output = Results(table=outputtable,display=ax)
    return output
#
def heatmap_status(df_state_beads,ordertracks,orderbeads):
    """
    (output resumeBeadsQuality, list,list) -> bokeh heatmap
    Input: df_resumeBeadsQuality is the output of the function
    resumeBeadsQuality, list of tracks order
    Output: bokeh heatmap with the status of the beads per track
    Example:
    heatmapGoodBadDetailed(df_resumeBeadsQuality,
                           order_tracks_chrono,
                           order_beads_best)
    """

    orderbeads = np.asarray(orderbeads)
    df_state_beads = df_state_beads.assign(
        mostCommonError =df_state_beads.set_index(
            ['bead', 'track']).idxmax(axis=1).values)
    df_state_beads = df_state_beads.assign(
        mostCommonError = np.where(df_state_beads.set_index(
            ['bead', 'track']).max(axis=1)==0,'noError',
                                   df_state_beads['mostCommonError']))
    df_state_beads = df_state_beads[['bead', 'track', 'mostCommonError']]
    plotbeads = orderbeads # df_state_beads['bead'].unique()
    plottracks = ordertracks
    aux = pd.DataFrame('', index=plottracks, columns=plotbeads)

    for bd in plotbeads:
        for trk in plottracks:
            aux.loc[trk][bd] = df_state_beads[
                    (df_state_beads['bead']==bd) & 
                    (df_state_beads['track']==trk)].mostCommonError.values[0]

    # reshape to 1D array
    df = pd.DataFrame(aux.stack(), columns=['typeError']).reset_index()
    iterativeTypeError = list(df['typeError'].unique())
    iterativeTypeError.remove('noError')
    iterativeTypeError.insert(0, 'noError')
    for i, err in enumerate(iterativeTypeError):
        df['typeError'] = np.where(df['typeError'] == err, int(i), df['typeError'])

    df.columns = ['track', 'bead', 'typeError']
    df['typeError'] = df['typeError'].apply(pd.to_numeric, errors='coerce')
    nberrors = df['typeError'].unique()
# colormap
    myreds = ["#B22222", "#8B008B", "#C71585", "#FF4500",
              "#CD6600", "#F08080", "#FF9912", "#B8860B",
              "#8A360F"]
    colors = ["#4169E1"] +  myreds[0:(len(nberrors)-2)] 

    
    mapper = LinearColorMapper(palette=colors, low=0, high=len(colors))
    #low=df.typeError.min(), high=df.typeError.max())
    labelsDict = dict(enumerate(iterativeTypeError))
    source = ColumnDataSource(df)
    df['bead'] = df['bead'].astype(str)
    TOOLS = "hover,save,pan,box_zoom,reset,wheel_zoom"

    plotbeads = plotbeads.astype(str) #change to string for the figure

    p = figure(plot_width=1000,
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
        line_color='grey')
    ############ to customize the color bar not used #########
    #def frange(start, stop, step):
    #    i = start
    #    while i < stop:
    #        yield i
    #        i+=step
    #myticks = []
    #for i in frange(0.5,len(colors),1):
    #    myticks.append(i)
    #ticker = FixedTicker(ticks = myticks)
    
    #formatter_keys = myticks
    #formatter_values = iterativeTypeError
    #formatter_dict = dict(zip(formatter_keys,formatter_values))

    #formatter_funct = FuncTickFormatter(code="""
    #    data = {0.5: a, 1.5:'b', 2.5:'c', 3.5:'d', 4.5:'e', 5.5:'f', 6.5:'g'}
    #    return data[tick]
    #""")
    ################## end customize not used #################

    color_bar = ColorBar(color_mapper=mapper,
                         major_label_text_font_size="10pt",
                         major_label_text_align = 'center',
                         #ticker=ticker, 
                         ticker = BasicTicker(desired_num_ticks=len(colors)),
                         #formatter=CategoricalTickFormatter(tags=iterativeTypeError),
                         formatter=PrintfTickFormatter(format="%s"),
                         #formatter = formatter_funct,
                         label_standoff=15,
                         border_line_color=None, location=(0, 0),
                         major_label_overrides= labelsDict,
                         major_tick_out=20
                          )
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
    
    colorDict =  {'noError':'#4169E1',
                  'fixed':'#FF6103',
                  'errors>=1':'#87CEEB',
                  'missing':'#CD0000'}

    df_sankey.reset_index()
    df_sankey = df_sankey.reset_index()[[first_track,last_track]]
    df_sankey
    sankey.sankey(df_sankey[first_track],df_sankey[last_track],
                  aspect=20,
                  colorDict=colorDict,
                  fontsize=12,
                  leftLabels=['errors>=1',
                              'fixed',
                              'missing',
                              'noError'],
                  rightLabels=['errors>=1',
                               'fixed',
                               'missing',
                               'noError'])
    plt.gcf().set_size_inches(12,12)
    plt.title('Track '+first_track+ r'$\longrightarrow$ Track '+last_track)
    #plt.savefig('sankey.png',bbox_inches='tight',dpi=150)
    return plt
