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
from assemble import data,mcscaler, shuffler
import assemble.scores as scores

class ScorePartition:
    'takes all paths from the partitions and scores each of them'

    def __init__(self,**kwa):
        self.ooverl=kwa.get("ooverl",-1) # type: int
        self.scoring=scores.ScoreAssembly(ooverl=self.ooverl)

    def __call__(self,partition)->Generator:
        for path in partition.paths():
            perm=data.OligoPerm.add(*path)
            kperm=data.OligoKPerm(oligos=perm.oligos,
                                  kperm=perm.perm,
                                  kpermids=perm.permids)
            yield self.scoring(kperm)



class Overseer(mcscaler.PeakSetting):
    '''
    manages scaler and shuffler
    defines a good sequence alignment
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        # self.oligos=kwa.get("oligos",[]) # type: List[data.OligoPeaks]
        # self.scaler=scaler.Scaler(oligos=self.oligos,
        #                            bbias=self.bbias,
        #                            bstretch=self.bstretch,
        #                            min_overl=self.min_overl)

        self.scaler=mcscaler.SeqHoppScaler(**kwa)
        # shift to  mcscaler.SeqHoppScaler(**self.__dict__)

        self.shuffler=shuffler.Shuffler() # not really necessary except for debugging
        # self.shuffler=shuffler.Shuffler(oligos=self.oligos,
        #                                 ooverl=self.min_overl)

        #self.score=ScorePartition(ooverl=self.min_overl)

    def run(self):
        '''
        main method
        stacks max_stack oligos
        can score the stacks as is
        runs shuffler (if necessary only) on each tuple of oligos
        discard worse solution
        resume
        '''
        partitions=[]

        for ite in range(5):
            print(f"ite={ite}")
            scales=self.scaler.run()
            # translate scales to peaks and to oligos
            scaled=[scales[2*idx]*self.peaks[idx]+scales[2*idx+1] for idx in range(len(self.peaks))]
            oligos=sorted([oli for peak in scaled for oli in peak.arr],
                          key=lambda x:x.pos)
            # each oligos is then separated by 1.1 nm

            # problem, havent considered signs of oligos...
            self.shuffler=shuffler.Shuffler(oligos=oligos,
                                            min_overl=self.min_overl)
            partitions.append(self.shuffler.run())
        return partitions
