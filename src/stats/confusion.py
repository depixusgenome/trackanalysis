#!/usr/bin/env python3
# -$- coding: utf-8 -$-
"Compute confusion matrix using the experiments and the real sequence"
import numpy            as np
import pandas           as pd
from scipy          import stats
import utilitaries as util
import sequences


class ConfusionMatrix:

    def __init__(self, data, oligos, seq_path, 
                 param_ioc,
                 param_tolerance):
        self.data = data
        self.tracknames = self.data.track.unique()
        seq = util.Seq()
        seq.set_sequence(seq_path)
        self.seq = seq
        self.oligos = oligos
        self.ioc = param_ioc
        self.tolerance = param_tolerance
        self.tolerance_minus = 0.01
        self.TP = 0
        self.FP = 0
        self.TN = 0
        self.FN = 0
        self.confusion_detail = pd.DataFrame()
        self.rule = 'theoretical_interval'
        self.brother = 3
        self.detection = list()#pd.DataFrame()


    def compute(self):
        self.get_detection()
        self.detection = pd.DataFrame(self.detection, columns = ['theopos',
                                                                 'exppos',
                                                                 'peaknb',
                                                                 'totalpeaks',
                                                                 'dist',
                                                                 'track',
                                                                 'oli',
                                                                 'strand',
                                                                 'brother',
                                                                 'rule',
                                                                 'detection',
                                                                 'hybrate',
                                                                 'hybtime'])
        df_grouped = list(self.detection.groupby(['theopos', 'track']))
        #compute the positions of the reference
        ref_pos = util.oligopeaks(self.seq.ref_oligo,
                                  self.seq)
        ref_pos = ref_pos[0] #only keep + strand positions
        list_results = list()

        for elem in df_grouped:
            #we use 'detection' feature, computed for each experimental peak
            #we compute the 'confusion_state' of the theoretical position if there is
            #detection in the estimators of each theoretical position
            if elem[1].strand.unique()[0]=='plus':
                confusion_state = 'TP' if any(elem[1].detection) else 'FN'
                estimators = len(elem[1].detection)
                good_estimators = sum(elem[1].detection)
                isref = True if elem[0][0] in ref_pos else False
            elif elem[1].strand.unique()[0]=='minus':
                confusion_state = 'TN' if not any(elem[1].detection) else 'FP'
                if confusion_state == 'FP':
                    confusion_state = 'TN' if sum(elem[1]['detection',
                                                          'brother'].isin[2]>0) else 'FP'
                estimators = len(elem[1].detection)
                good_estimators = sum(~elem[1].detection)
                isref = True if elem[0][0] in ref_pos else False
            try: 
                exp_pos = elem[1].exppos[elem[1].detection].unique()
            except IndexError:
                exp_pos = None
            list_results.append((elem[0][0], #theopos
                                 elem[0][1], #track
                                 exp_pos, #exppos
                                 elem[1].oli.unique()[0], #oligo
                                 elem[1].strand.unique()[0], #strand
                                 confusion_state,
                                 good_estimators,
                                 estimators,
                                 isref))
        self.confusion_detail = pd.DataFrame(list_results, columns = ['theopos',
                                                                      'track',
                                                                      'exppos',
                                                                      'oligo',
                                                                      'strand',
                                                                      'confusion_state',
                                                                      'nb_true_est',
                                                                      'total_est',
                                                                      'reference'])   



    def _get_peak_position_df(self, trk, strand = 'plus', metil = True):
        """
        output: auxiliary array to be used in get_detection with
                * experimental position of the peak
                * (closest theoretical position, index closest theoretical position,
                   brother (if strand=='minus'), nb of possible positions)
                * distance between experimental position and closest theoretical
                * data corresponding to experimental position
        """

        if metil: 
            theo_peaks = util.oligopeaks(util.map_track_oligo(trk, self.oligos),
                                    self.seq, hp = 'target')
        else:
            theo_peaks = util.oligopeaks(util.map_track_oligo(trk, self.oligos),
                                    self.seq, hp = 'complete')

        diffplusminus = [min(abs(theo_peaks[0] - minuspeak)) for minuspeak in theo_peaks[1]]
        theo_peaks = theo_peaks[0] if strand=='plus' else theo_peaks[1]

        databypeakposition = list(self.data[self.data.track==trk].groupby('peakposition'))

        peak_position = list()
        for peak in databypeakposition:
            if (strand=='minus' and len(theo_peaks)==0):
                continue
            idx = np.argmin(abs(theo_peaks - peak[0]))
            dist = -(theo_peaks - peak[0])[idx]
            if strand=='plus':
                peak_position.append((peak[0],
                                 (theo_peaks[idx], idx, len(theo_peaks)),
                                 dist,
                                 peak[1]))
                return peak_position
            if strand=='minus':
                brother = diffplusminus[idx] < self.brother 
                peak_position.append((peak[0],
                                 (theo_peaks[idx], idx, brother, len(theo_peaks)),
                                 dist,
                                 peak[1]))
                return peak_position

    def get_detection(self):
        for trk in self.tracknames:
            peakposition_plus = self._get_peak_position_df(trk, 'plus')
            peakposition_minus = self._get_peak_position_df(trk, 'minus')
            for peak in peakposition_plus:
                self._get_detection_perpeak(peak, 'plus')
            if peakposition_minus!=None:
                for peak in peakposition_minus:
                    self._get_detection_perpeak(peak, 'minus')


    def _get_detection_perpeak(self, peak, strand):
        """
        peak is a row from the output of _get_pea_position_df
        append to detection:
            * theoretical position
            * experimental position
            * theoretical peak number
            * total theoretical peaks for that strand
            * distance betweent theoretical and experimental position
            * track
            * oligo
            * strand
            * brother
            * rule
            * detection
            * hybridisation rate
            * average duration
        """
        ioc_theoretical_lower = peak[1][0] - self.ioc
        ioc_theoretical_upper = peak[1][0] + self.ioc
        prob_until_lower = stats.percentileofscore(peak[3].avg,
                                                   ioc_theoretical_lower)
        prob_until_upper = stats.percentileofscore(peak[3].avg,
                                                   ioc_theoretical_upper)
        
        if strand=='plus':
            brother = False
            if (prob_until_upper - prob_until_lower)/100 < self.tolerance:
                detecting = False
            else:
                detecting = True

        if strand == 'minus':
            brother = peak[1][2]
            if (prob_until_upper - prob_until_lower)/100 < self.tolerance_minus:
                detecting = False
            else:
                detecting = True
        
        self.detection.append((peak[1][0],
                               peak[0],
                               peak[1][1],
                               peak[1][2],
                               peak[2],
                               peak[3].track.unique()[0],
                               util.map_track_oligo(peak[3].track.unique()[0],
                                                  self.oligos),
                               strand,
                               brother,
                               self.rule,
                               detecting,
                               peak[3].hybridisationrate.unique()[0],
                               peak[3].averageduration.unique()[0]))
