#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utilitary functions"
import numpy        as np
import pandas       as pd
import warnings 
from scipy          import stats


class Seq:
    """The theoretical sequence: full, target, references"""

    def __init__(self):
        self.full = ''
        self.target = ''
        self.ref_oligo = ''

    def set_sequence(self, file_sequence):
        """file_sequence is the path of the fasta file
         format of the file:
            > full
            (...)cccatATTCGTATcGTcccat(...)
            > oligo
            cccat
            > target
            TCGTAT
        """
        myfile = open(file_sequence, 'r')
        text = myfile.read().replace('\n', '')
        myfile.close()

        self.full = text[text.find('full')+len('full'):text.find('> oligo')]
        self.ref_oligo = text[text.find('oligo')+len('oligo'):text.find('> target')]
        self.target = text[text.find('target')+len('target'):]

#    def __str__(self):
#        return """Theoretical sequence \n
#                  Full: \n {0} \n
#                  Target: \n {1} \n 
#                  Ref Oligo \n {2}""".format(str(self.full),str(self.target),str(self.ref_oligo))

def set_dict_oligo_trackname(oligos, names):
    """
    names is a list of the names of the tracks
    oligos is a list of the oligos to be considered
    """
    output = dict.fromkeys(oligos)
    for oli in output.keys():
        val = list()
        for trk_name in names:
            if oli in trk_name:
                val.append(trk_name)
                output[oli] = val
    if None in output.values():
        warnings.warn('There is an oligo with no track')
    return output

def set_dict_trackname_oligo(names, oligos):
    """
    oligos is a list of the oligos to be considered
    names is a list of the names of the tracks
    """
    output = dict.fromkeys(names)
    for trk_name in output.keys():
        output[trk_name] = map_track_oligo(trk_name, oligos)
    if '' in output.values():
        warnings.warn('There is a track with no oligo')
    return output

def map_track_oligo(name, oligos):
    lst = [name.upper().find(oli)>0 for oli in oligos]
    if sum(lst)==0:
        warnings.warn(f"""Can not find the oligo corresponding to track {name} \
in the set of oligos {oligos}""")
        return ''
    output = pd.DataFrame(oligos)[lst]
    if set(output[0].values)=={'OR3'}:
        output = 'OR3'
        return output
    if len(lst)>1:
        output = output[output != 'OR3']
        return output.dropna().values[0][0]
