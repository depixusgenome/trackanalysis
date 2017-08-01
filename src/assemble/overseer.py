#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
given some oligos
calls scaler (which does not yet alloow for non-linearity)
then calls shuffler (which also scores the builded stack)
need to compute only tuple(oligos) for each key (many duplicate possible)

What could be done frfom here:

Either scaler is general and takes into account non-linearities
in which cases we can score easily the partitions
and may not even need shuffler (until FP or FN kicks in)

Or non-linearities is included in the gaussian noise
more difficult to implement but simpler algorithm as a whole
'''

from typing import List, Generator # pylint: disable=unused-import
import assemble.scaler as ascaler
import assemble.shuffler as ashuffler
import assemble.data as adata  # pylint: disable=unused-import
import assemble.scores as scores

class ScorePartition:
    'takes all paths from the partitions and scores each of them'

    def __init__(self,**kwa):
        self.ooverl=kwa.get("ooverl",-1) # type: int
        self.scoring=scores.ScoreAssembly(ooverl=self.ooverl)

    def __call__(self,partition)->Generator:
        for path in partition.paths():
            perm=adata.OligoPerm.add(*path)
            kperm=adata.OligoKPerm(oligos=perm.oligos,
                                   kperm=perm.perm,
                                   kpermids=perm.permids)
            yield self.scoring(kperm)

class BaseOverseer:
    'Overseer Parent Class'
    def __init__(self,**kwa):
        self.min_overl=kwa.get("min_overl",2) # type: int
        self.bbias=kwa.get("bbias",ascaler.Bounds())
        self.bstretch=kwa.get("bstretch",ascaler.Bounds())
        self.maxstack=kwa.get("maxstack",4) # type: int

class Overseer(BaseOverseer):
    '''
    manages scaler and shuffler
    defines a good sequence alignmenent
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.oligos=kwa.get("oligos",[]) # type: List[adata.OligoPeaks]
        self.scaler=ascaler.Scaler(oligos=self.oligos,
                                   bbias=self.bbias,
                                   bstretch=self.bstretch,
                                   min_overl=self.min_overl)
        self.shuffler=ashuffler.Shuffler(oligos=self.oligos,
                                         ooverl=self.min_overl)

        self.score=ScorePartition(ooverl=self.min_overl)

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
        print(f"len(stacks)={len(stacks)}")
        # toshuffle=list(frozenset(tuple (val) for stack in stacks for val in stack.stack.values()))
        # pathscores=[] # type: List[scores.ScoredPerm]
        # for elmt in toshuffle:
        #     if len(elmt)>1:
        #         partitions=self.shuffler.run(oligos=elmt)
        #         for partition in partitions:
        #             pathscores+=list(self.score(partition))

        #         # do not score partitions, but stacks of oligos
        #         # score stacks ... or only tuple of oligos
        #         # score tuple and discard all tuple who have a score
        #         # overlapping is already considered.  for each stack.
        #         # careful.
        #         # overlapping may not be maximal if non-linearity is implemented in stacking!
        #         # need to score each partitions and the ambiguities (overlap + pdfcost)


        # discard unwanted partitions
        # for _ in range(5):
        #     print(f"iterating scaler resume {_}")
        #     stacks=self.scaler.resume(pstacks=stacks,iteration=self.maxstack)
        #     print(f"len(stacks)={len(stacks)}")
        return stacks
