#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
given some oligos
calls scaler (which does not yet alloow for non-linearity)
then calls shuffler (which also scores the builded stack)
need to compute only tuple(oligos) for each key (many duplicate possible)
'''

from typing import List # pylint: disable=unused-import
import assemble.scaler as ascaler
import assemble.shuffler as ashuffler
import assemble.data as adata  # pylint: disable=unused-import

class Overseer:
    '''
    manages scaler and shuffler
    defines a good sequence alignmenent
    '''
    def __init__(self,**kwa):
        self.oligos=kwa.get("oligos",[]) # type: List[adata.OligoPeaks]
        self.min_overl=kwa.get("min_overl",2) # type: int
        self.bbias=kwa.get("bbias",ascaler.Bounds())
        self.bstretch=kwa.get("bstretch",ascaler.Bounds())
        self.maxstack=kwa.get("maxstack",4) # type: int
        self.scaler=ascaler.Scaler(oligos=self.oligos,
                                   bbias=self.bbias,
                                   bstretch=self.bstretch,
                                   min_overl=self.min_overl)
        self.shuffler=ashuffler.Shuffler(oligos=self.oligos,
                                         ooverl=self.min_overl)

    def run(self):
        '''
        main method
        stacks max_stack oligos
        can score the stacks as is
        runs shuffler (if necessary only) on each tuple of oligos
        discard worse solution
        resume
        '''
        stacks=self.scaler.run(iteration=self.maxstack)
        toshuffle=list(frozenset(tuple (val) for stack in stacks for val in stack.stack.values()))
        # for elmt in toshuffle:
        #     if len(elmt)>1:
        #         self.shuffler.run(oligos=elmt)

        return toshuffle
