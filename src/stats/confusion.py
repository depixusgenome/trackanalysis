#!/usr/bin/env python3
# -$- coding: utf-8 -$-
"Compute confusion matrix using the experiments and the real sequence"
import numpy            as np
import pandas           as pd
from scipy          import stats

class ConfusionMatrix:

    def __init__(self, data, oligos, seq_path,
                 param_rule,
                 param_brother,
                 param_confidence,
                 param_ioc,
                 param_tolerance):
        self.data = data
        self.tracknames = self.data.track.unique()
        seq = Seq()
        seq.set_sequence()
        self.seq = seq
        self.oligos = oligos
        self.TP = 0
        self.FP = 0
        self.TN = 0
        self.FN = 0
        self.confusion_detail = pd.DataFrame()
        self.rule = param_rule
        self.brother = param_brother
        self.confidence = param_confidence
        self.ioc = param_ioc
        self.tolerance = param_tolerance
        self.detection = pd.DataFrame()


    def compute(self):
        df_grouped = list(self.df_detection.groupby(['theopos', 'track']))
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
                                                                      'nb_true_est',
                                                                      'total_est',
                                                                      'reference'])   



    def _get_peak_position_df():
        """
        output: auxiliary pandas DataFrame to be used in compute_qualities ?"""


