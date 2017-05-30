#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u'''
Creates Classes and function to use with assemble sequence
'''
from typing import List, NamedTuple, Tuple
import itertools
import numpy
from utils import initdefaults
from ._types import SciDist # pylint: disable=unused-import
from . import _utils as utils


class Oligo:
    u'''
    container for an oligo sequence, a position in nanometer
    and a position in base
    '''
    seq="" # type: str
    pos=-1 # type: int
    bpos=-1 # type: int # base position
    @initdefaults
    def __init__(self,**kwa):
        pass
    @property
    def size(self):
        u'returns len(seq)'
        return len(self.seq)

    @staticmethod
    def tail_overlap(ol1:str, ol2:str)->str:
        u'''
        returns the end sequence of ol1 matching the start of ol2
        '''
        for i in range(len(ol1)):
            if ol1[i:]==ol2[:len(ol1)-i]:
                return ol1[i:]
        return ""

    def add_to_sequence(self,seq:str)->str:
        u'''
        returns the sequence such that overlap of seq and oseq is maximised
        '''
        if self.seq=="":
            return seq
        i=0 # if seq==""
        for i in range(len(seq)):
            if seq[i:]==self.seq[:len(seq)-i]:
                return seq[:i]+self.seq
        return seq+self.seq

class OligoPeak(Oligo):
    u'represents peaks obtained from sequencing experiment'
    batch_id = -1 # type: int
    dist = None # type: SciDist
    poserr = -1. # type: float
    # initial (experimental) position in nanometer
    pos0 = -1. # type : float
    # initial (experimental) base position
    bpos0 = -1. # type : float
    @initdefaults
    def __init__(self,**kwa):
        super().__init__(**kwa)

OliBat = NamedTuple("OliBat",[("oli",OligoPeak),
                              ("idinbat",int),
                              ("batid",int)])

class Batch:
    u'''
    Container for Oligo
    could setattr BCollection id to each oligo
    '''
    oligos=[] # type: List[OligoPeak]
    index=-1 # type: int
    @initdefaults
    def __init__(self,**kwa):
        pass

    def fill_with(self,other)->None:
        u'adds oligos from other into self and empties other'
        self.oligos.extend(other.oligos)
        del other.oligos

    def oligo_overlap(self,other,min_overl:int=1)->bool:
        u'''
        compare the sequences of oligos in the two batch
        if any can tail_overlap
        return True
        else return False
        '''
        oli1 = set(oli.seq for oli in self.oligos)
        oli2 = set(oli.seq for oli in other.oligos)
        for ite in itertools.product(oli1,oli2):
            if len(Oligo.tail_overlap(ite[0],ite[1]))>=min_overl:
                return True
            if len(Oligo.tail_overlap(ite[1],ite[0]))>=min_overl:
                return True

        return False

class BCollection:
    u'''
    Collection of batches
    '''
    oligos = [] # type: List[OligoPeak]
    batches = [] # type: List[Batch]
    @initdefaults
    def __init__(self,**kwa):
        pass

    @classmethod
    def from_oligos(cls,oligos:List[OligoPeak],attr="seq"): # read process (to processor)?
        u'from a list of OligoPeaks, creates BCollection'
        grps= {getattr(oli,attr) for oli in oligos}
        batches=[Batch(oligos=[oli for oli in oligos if getattr(oli,attr)==grp],index=idx)
                 for idx,grp in enumerate(grps)]
        return cls(oligos=oligos,batches=batches)

    def group_overlapping_oligos(self,nscale)->List[List[OligoPeak]]:
        u'returns groups of overlapping oligos'
        groups = utils.group_overlapping_normdists([oli.dist for oli in self.oligos],
                                                   nscale=nscale)[1]
        return [[self.oligos[idx] for idx in grp] for grp in groups]

    def group_overlapping_batches(self,nscale)->List[List[OligoPeak]]:
        u'same as group_overlapping_oligos except that only oligos in batches are considered'
        olis=[] # type: List[OligoPeak]
        for bat in self.batches:
            olis+=bat.oligos
        groups = utils.group_overlapping_normdists([oli.dist for oli in olis],
                                                   nscale=nscale)[1]
        return [[olis[idx] for idx in grp] for grp in groups]


    def oli2index(self,oli:OligoPeak)->int:
        u'returns index of oli in oligos'
        return self.oligos.index(oli)


class OligoPerm:
    u'base class. full n-permutation'
    def __init__(self,**kwa):
        self.oligos=kwa.get("oligos",[]) # type: List[OligoPeak]
        self.__changes = kwa.get("changes",tuple()) # type: Tuple[int, ...]
        self.__perm = kwa.get("perm",[]) # type: List[OligoPeak]
        self.__permids = kwa.get("permids",numpy.array([],dtype=int)) # type: List[int]
        self.__domain =  kwa.get("domain",set()) # type: Set[int]

    @property
    def permids(self):
        u'returns value'
        return self.__permids

    @property
    def perm(self):
        u'perm may not be needed, compute iff necessary'
        if self.__perm==[]:
            self.__perm=numpy.array(self.oligos)[self.permids].tolist()
        return self.__perm

    @property
    def changes(self):
        u'returns value'
        return self.__changes

    @property
    def domain(self):
        u'returns value'
        return self.__domain

    @classmethod
    def add(cls,*args):
        u'''
        add all perms in args
        perm args[0] applied first,
        then args[1], args[2], ...
        if args=(,)?
        if len(args)==1 ?
        '''
        if len(args)==1:
            return args[0]

        res = cls.__add2(*args[:2])
        for perm in args[2:]:
            res = cls.__add2(res,perm)
        return res

    @classmethod
    def __add2(cls,perm1, perm2):
        u'''
        combine 2 OligoPerms
        assumes that the 2 perms have the same oligos
        '''
        if len(set(perm1.domain).intersection(set(perm2.domain)))>0:
            raise ValueError("perm1 and perm2 are not independant")
        changes = perm1.changes+perm2.changes
        permids = perm1.permids[perm2.permids]
        perm=[]
        if not perm1.oligos==[]:
            perm=[perm1.oligos[i] for i in permids]
        return OligoPerm(oligos=perm1.oligos,
                         changes=changes,
                         perm=perm,
                         permids=permids,
                         domain=perm1.domain.union(perm2.domain))


    # TO CHECK! Expand pytest
    def outer_seqs(self,ooverl:int)->Tuple[str, ...]:
        u'''
        returns the overlapping oligo seq of left most oligo and right most
        as a tuple(left,right)
        '''
        changed=[val in self.changes for idx,val in enumerate(self.permids)]

        # "l" for left, take the first ooverl chars in sequence
        # "r" for right
        sides=[("l",0)] if changed[0] else []
        for idx,val in enumerate(changed[1:]):
            if changed[idx]!=val:
                if changed[idx]:
                    sides.append(("r",idx))
                else:
                    sides.append(("l",idx+1))
        if changed[-1]:
            sides.append(('r',len(changed)-1))

        return tuple(self.perm[val].seq[:ooverl]
                     if lorr=="l"
                     else self.perm[val].seq[-ooverl:]
                     for lorr,val in sides)


class OligoKPerm(OligoPerm):
    u'''
    kpermutation of OligoPeak Object
    As soon as 2 OligoKPerms are combine we work on OligoPerm objects
    '''
    def __init__(self,**kwa)->None:
        super().__init__(**kwa)
        self.kperm=kwa.get("kperm",[]) # type: List[OligoPeak]
        self.__kpermids = kwa.get("kpermids",numpy.array([],dtype=int)) # type: numpy.array

    @property
    def kpermids(self)->List[int]:
        u'returns the indices of the kperm'
        if self.__kpermids==[]:
            self.__kpermids=[self.oligos.index(oli) for oli in self.kperm]
        return self.__kpermids

    @property
    def perm(self):
        u'returns full permutation of oligos'
        if self.__perm==[]:
            self.__perm=numpy.array(self.oligos)[self.permids].tolist()
        return self.__perm

    @property
    def permids(self):
        u'returns the full permutation of oligo indices'
        if self.__permids==[]:
            toperm={val:self.kpermids[idx] for idx,val in enumerate(sorted(self.kpermids))}
            self.__permids=list(range(len(self.oligos)))
            for key,val in toperm.items():
                self.__permids[key]=val
        return self.__permids

    @classmethod
    def get_changes(cls,kperm,sort_by="pos")->Tuple[int, ...]:
        u'''
        returns the smallest (contiguous) permutations of kperm
        will not work for a combination of kperms
        '''
        try:
            sortedp=sorted(kperm,key=lambda x:getattr(x,sort_by))
        except AttributeError:
            sortedp=sorted(kperm)
        issame=[sortedp[idx]==kperm[idx] for idx in range(len(kperm))]

        try:
            if issame[-1] is False:
                return tuple(kperm[issame.index(False):])
            return tuple(kperm[issame.index(False):-list(reversed(issame)).index(False)])
        except ValueError:
            return tuple()

    @property
    def domain(self):
        u'returns the set of indices onto which the k-permutation applies'
        if self.__domain==set():
            self.__domain=set(self.kpermids)
        return self.__domain

    @property
    def changes(self)->Tuple[int, ...]:
        u'''
        returns the tuple of indices which will be changed by application of perm
        should return [] if all sorted(perm)[i]==perm[i], ie: identity operator
        '''
        if self.__changes==tuple():
            self.__changes=self.get_changes(self.kpermids)
        return self.__changes

class Permids2OligoPerm:
    u'Convertion class'
    oligos=[] # type: List[OligoPeak]
    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        u'initialize before call'
        pass
    def __call__(self,permids:List[int])->OligoPerm:
        u'convert using permids'
        # leaves perms list iff necessary
        return OligoPerm(oligos=self.oligos,
                         permids=permids,
                         changes=,
                         domain=)


# replace with OligoPerm
class KPermCollection:
    u'''
    Container for a list of OligoKPerm
    '''
    kperms=[] # type: List[OligoKPerm]

    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    @classmethod
    def product(cls,*args):
        u'''
        returns a KPermCollection with the product of kperms in first
        and kperms in second
        '''
        if len(args)==1:
            return args[0]

        res = cls.__product2(*args[:2])
        for kpc in args[2:]:
            res = cls.__product2(res,kpc)
        return res

    @classmethod
    def __product2(cls,first,second):
        u'''
        takes the product of 2 elements at a time
        '''
        kperms = list(OligoKPerm.add(*prd)
                      for prd in itertools.product(first.kperms,second.kperms))
        return cls(kperms=kperms)


    def intersect_with(self,other):
        u'''
        returns True if any OligoKPerm is shared by the 2 collections
        REMINDER: 2 groups intersecting (i.e. which share the same oligos)
        both contain the kperm related to the intersecting oligos.
        So one has to consider only 1 of the 2 intersecting subgroups.
        '''
        for kpr in self.kperms:
            if any(set(kpr.kperm).intersection(set(oth.kperm)) for oth in other.kperms):
                return True
        return False
