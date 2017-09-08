#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
given some oligos
calls scaler (which does not yet alloow for non-linearity)
then calls shuffler (which also scores the builded stack)
need to compute only tuple(oligos) for each key (many duplicate possible)

What could be done from here:

Either scaler is general and takes into account non-linearities
in which cases we can score easily the partitions
and may not even need shuffler (until FP or FN kicks in)

Or non-linearities is included in the gaussian noise
more difficult to implement but simpler algorithm as a whole
'''

from typing import List, Generator, Tuple # pylint: disable=unused-import
import pickle
import itertools
import networkx
from assemble import data,mcscaler, shuffler
from assemble.settings import PeakSetting
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

class Overseer(PeakSetting):
    '''
    manages scaler and shuffler
    defines a good sequence alignment
    '''
    def __init__(self,**kwa):
        super().__init__(**kwa)
        self.scaler=mcscaler.SpringScaler(**kwa)# mcscaler.SeqHoppScaler(**kwa)
        self.shuffler=shuffler.Shuffler()
        self.signed_oligos:List[data.OligoPeak]

    @staticmethod
    def fix_signs(oligos:List[data.OligoPeak],min_overl:int=2): # ->List[data.OligoPeak]:
        '''
        fix signs of ordered oligos such that
        the # of overlaps is maximize

        Listing all_shortest_paths might not be necessary in the present
        case and could be replaced by shortest_path, to convince

        actually no need to use networkx
        (from the source always take the best neighbor?)
        will have to rewrite it without networkx to run in scoring

        '''
        def func(seq1,seq2):
            "local call to overlap"
            return data.Oligo.overlap(seq1,seq2,min_overl=min_overl,signs=(1,1),shift=1)
        graph=networkx.DiGraph()
        #oligos=sorted(oligos,key:lambda x:x.pos)
        edges=[(oligos[idx],val) for idx,val in enumerate(oligos[1:])]
        edges+=[(oligos[idx].reverse(in_place=False),val) for idx,val in enumerate(oligos[1:])]
        sources=[edges[0][0],edges[len(oligos)-1][0]]
        edges+=[(oligos[idx],val.reverse(in_place=False)) for idx,val in enumerate(oligos[1:])]
        targets=[oligos[-1],edges[-1][1]]
        edges+=[(oligos[idx].reverse(in_place=False),val.reverse(in_place=False))
                for idx,val in enumerate(oligos[1:])]
        # weight is 1 if no overlap, 0 otherwise, shortest path problem
        weights=[0 if func(ed1.seq,ed2.seq) else 1 for ed1,ed2 in edges]
        graph.add_edges_from([edges[idx]+({"weight":weights[idx]},) for idx in range(len(edges))])
        paths:List[Tuple[float,List[data.OligoPeak]]]=[]

        for src,tgt in itertools.product(sources,targets):
            paths+=[(networkx.shortest_path_length(graph,src,tgt,weight="weight"),
                     list(networkx.shortest_path(graph,source=src,target=tgt,weight="weight")))]

            # all shortest paths is not a solution, too long!
        return sorted(paths,key=lambda x:x[0])[0][1]

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
            scaled=self.scaler.run()
            # translate scales to peaks and to oligos
            # scaled=[scales[2*idx]*self.peaks[idx]+scales[2*idx+1]
            # for idx in range(len(self.peaks))]
            # oligos=sorted([oli for peak in scaled for oli in peak.arr],
            #               key=lambda x:x.pos)
            # each oligos is then separated by 1.1 nm

            oligos=self.scaler.ordered_oligos(scaled)
            if self.unsigned:
                self.signed_oligos=self.fix_signs(oligos,self.min_overl)
            else:
                self.signed_oligos=oligos

            if __debug__:
                # to debug error in line 219 of shuffler
                pickle.dump(self.signed_oligos,open(f"dbgsigned{ite}.pickle","wb"))
            self.shuffler=shuffler.Shuffler(oligos=self.signed_oligos,
                                            ooverl=self.min_overl)
            partitions.append(self.shuffler.run())
        return partitions
