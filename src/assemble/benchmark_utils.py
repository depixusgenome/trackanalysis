#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
a series of functions, classes to call from notebooks
test oligohits created
import pickle
import copy
testoligohits=[copy.deepcopy(i) for i in oligohits] # to del
for idx,oli in enumerate(testoligohits):# to del
oli.pos=init[idx]# to del
print("oligoseq=",oli.seq)# to del
print("experimental position=",oli.pos)# to del
with open("./oligohits_for_Vincent.pickle","wb") as outfile:# to del
pickle.dump(testoligohits,outfile) # to del
return # to del
'''
import random
import scipy.stats
from assemble import oligohit, assemble

def random_sequence(length=100):
    u'generates a random sequence'
    return "".join(random.choice("atcg") for i in range(length))

def sequence2oligohits(seq,size,overlap):
    u'''given a sequence, size and overlap of oligos returns a list corresponding oligohits'''
    # compute sequences of oligos
    oliseqs = [seq[i:i+size] for i in range(0,len(seq),size-overlap)]
    return [oligohit.OligoHit(seq=val,
                              pos=idx*(size-overlap),
                              pos0=idx*(size-overlap),
                              bpos=idx*(size-overlap),
                              bpos0=idx*(size-overlap)) for idx,val in enumerate(oliseqs)]


def create_benchmark(nrecs=1,  # pylint: disable=too-many-arguments,too-many-locals
                     oli_size=10,
                     exp_err=3,
                     overlap=2,
                     seq_length=100,
                     energy_func=None,
                     tooligo_func=None,
                     pname="benchmark"):
    u'''
    returns a list of nrecs recorders with the same random sequence
    exp_err in number of base pairs
    '''
    noise = scipy.stats.truncnorm(a=-10/exp_err,b=10/exp_err,loc=0.0,scale=exp_err).rvs
    recorders = []
    # generate sequence
    sequence = random_sequence(seq_length)
    # create oligohits
    oligohits = sequence2oligohits(seq=sequence,size=oli_size,overlap=overlap)
    wrapper = assemble.OligoWrap(oligohits,tooligo_func)
    for rec_it in range(nrecs):
        # create state_init
        init = [i.pos+noise() for i in oligohits]
        # customized distribution for hopping steps
        dists = [scipy.stats.norm(loc=i,scale=exp_err) for i in init]
        hopp_steps = assemble.PreFixedSteps(dists=dists)
        assembler = assemble.MCAssemble(state_init=init,
                                        func=wrapper(energy_func),
                                        step=hopp_steps)
        recorders.append(assemble.SeqRecorder(sequence=sequence,
                                              oligohits=oligohits,
                                              assembler=assembler,
                                              filename=pname+str(rec_it)+".pickle"))

    return recorders

class Benchmark: # pylint: disable=too-many-instance-attributes
    u'''
    creates a class to benchmark chosen values of the assembler class
    not finished
    '''
    def __init__(self,**kwargs):
        self.assemble_class=kwargs.get("assemble_class",assemble.MCAssemble)
        self.rec_class=kwargs.get("rec_class",assemble.Recorder)
        self.step_class=kwargs.get("step_class",assemble.HoppingSteps)
        self.seq=kwargs.get("seq","")
        self.overlaps=kwargs.get("overlaps",[2])
        self.sizes=kwargs.get("sizes",[10])
        self.name=kwargs.get("name","benchmark")
        self._setup()

    def _setup(self):
        self.olihits = []
        self.inits = []
        self.assembles = []
        self.recs = []
        for size,overlap in zip(self.sizes,self.overlaps):
            olih=sequence2oligohits(self.seq,size,overlap)
            init=[i.bpos for i in olih]
            self.olihits.append(olih)
            self.inits.append(init)
            step = self.step_class()
            self.assembles.append([self.assemble_class(state_init=init,
                                                       func=None,
                                                       niter=None,
                                                       step=step)])
            self.recs.append([])
    def run(self):
        u'run each recorder'
        for recit in self.recs:
            recit.run()
