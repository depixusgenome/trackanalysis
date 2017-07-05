#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Creates Classes and function to use with assemble sequence
'''
from typing import List, NamedTuple, Tuple, FrozenSet, Set, Dict # pylint: disable=unused-import
import itertools
import numpy
from utils import initdefaults
from ._types import SciDist # pylint: disable=unused-import
from . import _utils as utils

REVERSE={"a":"t","c":"g","g":"c","t":"a"}

class Oligo:
    '''
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
        'returns len(seq)'
        return len(self.seq)

    @staticmethod
    def reverse_complement(seq)->str:
        'returns reverse complement of string seq'
        return ''.join(REVERSE[i] for i in reversed(seq))

    @staticmethod
    def tail_overlap(ol1:str, ol2:str)->str:
        '''
        returns the end sequence of ol1 matching the start of ol2
        '''
        for i in range(len(ol1)):
            if ol1[i:]==ol2[:len(ol1)-i]:
                return ol1[i:]
        return ""

    def add_to_sequence(self,seq:str)->str:
        '''
        returns the sequence such that overlap of seq and oseq is maximised
        '''
        if self.seq=="":
            return seq
        i=0 # if seq==""
        for i in range(len(seq)):
            if seq[i:]==self.seq[:len(seq)-i]:
                return seq[:i]+self.seq
        return seq+self.seq

# it is bpos which needs to be updated
# If 2 oligos are too far from one another there is a
# unknown number of bases between the 2
# because of this the stretch is unknown (lower or higher bound known though)
# If the contiguous set of oligos of unknown stretch contains an oligo
# from the same batch as another
# we can reestimate the stretch bias
# Should we modify the bias?
class OligoPeak(Oligo):
    'represents peaks obtained from sequencing experiment'
    batch_id = -1 # type: int
    dist = None # type: SciDist
    poserr = -1. # type: float
    # initial (experimental) position in nanometer
    pos0 = -1. # type: float
    # initial (experimental) base position
    bpos0 = -1. # type: float
    bpos = 0 # type: int
    appliedstretch = 1 # type: float
    appliedbias = 0 # type: float
    @initdefaults
    def __init__(self,**kwa):
        super().__init__(**kwa)

    @property
    def bias(self):
        'returns bias'
        return self.appliedbias

    @property
    def stretch(self):
        '''
        recomputes stretch from current position
        takes into account modifications due to permutations
        '''
        try:
            return (self.bpos-self.bias)/self.pos
        except ZeroDivisionError:
            return 0


OliBat = NamedTuple("OliBat",[("oli",OligoPeak),
                              ("idinbat",int),
                              ("batid",int)])

class Batch:
    '''
    Container for Oligo
    could setattr BCollection id to each oligo
    '''
    oligos=[] # type: List[OligoPeak]
    index=-1 # type: int
    @initdefaults
    def __init__(self,**kwa):
        pass

    def fill_with(self,other)->None:
        'adds oligos from other into self and empties other'
        self.oligos.extend(other.oligos)
        del other.oligos

    def oligo_overlap(self,other,min_overl:int=1)->bool:
        '''
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
    '''
    Collection of batches
    '''
    oligos = [] # type: List[OligoPeak]
    batches = [] # type: List[Batch]
    idsperbatch = dict() # type: Dict[int,List[int]]
    @initdefaults
    def __init__(self,**kwa):
        pass

    @classmethod
    def from_oligos(cls,oligos:List[OligoPeak],attr="seq"):
        'from a list of OligoPeaks, creates BCollection'
        grps= {getattr(oli,attr) for oli in oligos}
        batches=[Batch(oligos=[oli for oli in oligos if getattr(oli,attr)==grp],index=idx)
                 for idx,grp in enumerate(grps)]
        idsperbatch={grpid:[idx for idx,oli in enumerate(oligos) if getattr(oli,attr)==grp]
                     for grpid, grp in enumerate(grps)}
        return cls(oligos=sorted(oligos,key=lambda x:x.pos),# oligos=oligos,
                   batches=batches,
                   idsperbatch=idsperbatch)

    def group_overlapping_oligos(self,nscale)->List[List[OligoPeak]]:
        'returns groups of overlapping oligos'
        groups = utils.group_overlapping_normdists([oli.dist for oli in self.oligos],
                                                   nscale=nscale)[1]
        return [[self.oligos[idx] for idx in grp] for grp in groups]

    def group_overlapping_batches(self,nscale)->List[List[OligoPeak]]:
        'same as group_overlapping_oligos except that only oligos in batches are considered'
        olis=[] # type: List[OligoPeak]
        print("nscale=",nscale)
        for bat in self.batches:
            olis+=bat.oligos
        groups = utils.group_overlapping_normdists([oli.dist for oli in olis],
                                                   nscale=nscale)[1]
        return [[olis[idx] for idx in grp] for grp in groups]

    def oli2index(self,oli:OligoPeak)->int:
        'returns index of oli in oligos'
        return self.oligos.index(oli)


class OligoPerm:
    'base class. full n-permutation'
    def __init__(self,**kwa):
        self.oligos=kwa.get("oligos",[]) # type: List[OligoPeak]
        #self._changes = kwa.get("changes",tuple()) # type: Tuple[int, ...]
        self._perm = kwa.get("perm",[]) # type: List[OligoPeak]
        self._permids = kwa.get("permids",numpy.empty(0,dtype='i4')) # type: List[int]
        self._domain =  kwa.get("domain",frozenset()) # type: FrozenSet[int]

    @property
    def permids(self):
        'returns value'
        return self._permids

    @property
    def perm(self):
        'perm may not be needed, compute iff necessary'
        if len(self._perm)==0:
            self._perm=numpy.array(self.oligos)[self.permids].tolist()
        return self._perm

    @property
    def changes(self):
        'returns value'
        #return self._changes
        return tuple(self._domain)

    @property
    def domain(self):
        'returns value'
        return self._domain

    @classmethod
    def add(cls,*args):
        '''
        add all perms in args
        perm args[0] applied first,
        then args[1], args[2], ...
        if args=(,)?
        if len(args)==1 ?
        '''
        if len(args)==1:
            return args[0]

        res = cls.__add2(args[0],args[1])
        for perm in args[2:]:
            res = cls.__add2(res,perm)
        return res

    @classmethod
    def __add2(cls,perm1, perm2):
        '''
        combine 2 OligoPerms
        assumes that the 2 perms have the same oligos
        '''
        if __debug__:
            if len(frozenset(perm1.domain).intersection(frozenset(perm2.domain)))>0:
                print("perm1.domain",perm1.domain)
                print("perm2.domain",perm2.domain)
                raise ValueError("perm1 and perm2 are not independant")
        #changes = perm1.changes+perm2.changes
        permids = perm1.permids[perm2.permids]
        perm=[]
        if not len(perm1.oligos)==0:
            perm=[perm1.oligos[i] for i in permids]
        return OligoPerm(oligos=perm1.oligos,
                         perm=perm,
                         permids=permids,
                         domain=perm1.domain.union(perm2.domain))

    def __hash__(self)->int:
        return hash((tuple(sorted(self.domain)),tuple(self.permids)))

    def __eq__(self,other)->bool:
        if isinstance(other,OligoPerm) and self.__hash__()==other.__hash__():
            return True
        return False

    def __del__(self):
        del self.oligos
        del self._perm
        del self._permids
        del self._domain

class Partition:
    'container for indepent OligoPerm objects'
    perms=[]  # type: List[OligoPerm]
    scores=tuple() # type: Tuple[float, ...]
    noverlaps=0 # type: int
    pdfcost=0 # type: float
    @initdefaults
    def __init__(self,**kwa):
        pass

    def merge(self)->OligoPerm:
        'returns the merged perms'
        return OligoPerm.add(*self.perms)

    def add(self,perm:OligoPerm,in_place=False):
        '''
        returns a new Partition with added perm
        if in_place==True appends perms with perm
        '''
        if in_place:
            self.perms+=[perm]
        else:
            return self.__copy__(perms=self.perms+[perm])

    def __copy__(self,perms=None):
        'returns copied Partition'
        if perms is None:
            return Partition(**self.__dict__)
        return Partition(perms=perms,
                         scores=self.scores,
                         noverlaps=self.noverlaps,
                         pdfcost=self.pdfcost)

class OligoKPerm(OligoPerm):
    '''
    kpermutation of OligoPeak Object
    As soon as 2 OligoKPerms are combine we work on OligoPerm objects
    '''
    def __init__(self,**kwa)->None:
        super().__init__(**kwa)
        self.kperm=kwa.get("kperm",[]) # type: List[OligoPeak]
        self._kpermids = kwa.get("kpermids",numpy.empty(0, dtype='i4')) # type: numpy.array

    @property
    def kpermids(self)->List[int]:
        'returns the indices of the kperm'
        if len(self._kpermids)==0:
            self._kpermids=[self.oligos.index(oli) for oli in self.kperm]
        return self._kpermids

    @property
    def perm(self):
        'returns full permutation of oligos'
        if len(self._perm)==0:
            self._perm=numpy.array(self.oligos)[self.permids].tolist()
        return self._perm

    @property
    def permids(self):
        'returns the full permutation of oligo indices'
        if len(self._permids)==0:
            toperm={val:self.kpermids[idx] for idx,val in enumerate(sorted(self.kpermids))}
            self._permids=numpy.array(range(len(self.oligos)))
            for key,val in toperm.items():
                self._permids[key]=val
        return self._permids

    # not used anymore
    @classmethod
    def get_changes(cls,kperm,sort_by="pos")->FrozenSet[int]:
        '''
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
                return frozenset(kperm[issame.index(False):])
            return frozenset(kperm[issame.index(False):-list(reversed(issame)).index(False)])
        except ValueError:
            return frozenset()

    @classmethod
    def get_domain(cls,kperm,sort_by="pos")->FrozenSet[int]:
        '''
        return the elements of kperm which are changed by application of the kpermutation
        '''
        try:
            sortedp=sorted(kperm,key=lambda x:getattr(x,sort_by))
        except AttributeError:
            sortedp=sorted(kperm)
        issame=[sortedp[idx]==kperm[idx] for idx in range(len(kperm))]
        return frozenset(val for idx,val in enumerate(kperm) if not issame[idx])

    @property
    def domain(self):
        'returns the set of indices onto which the k-permutation applies'
        if len(self._domain)==0:
            self._domain=self.get_domain(self.kpermids)
        return self._domain

    @property
    def changes(self)->Tuple[int, ...]:
        '''
        returns the tuple of indices which will be changed by application of perm
        should return [] if all sorted(perm)[i]==perm[i], ie: identity operator
        '''
        return tuple(self.domain)

    def __hash__(self)->int:
        return hash((tuple(sorted(self.domain)),tuple(self.kpermids)))

    def __eq__(self,other)->bool:
        if isinstance(other,OligoKPerm) and self.__hash__()==other.__hash__():
            return True
        return False

    # to check
    def identity_perm(self):
        '''
        returns an OligoKPerm with identity permutation
        but with same domain
        '''
        skperm = sorted(zip(self.kpermids,self.kperm))
        return OligoKPerm(oligos=self.oligos,
                          kperm=[i[1] for i in skperm],
                          kpermids=[i[0] for i in skperm],
                          domain=self.domain)

    def __del__(self):
        del self.kperm
        del self._kpermids


# replaced by OligoPerm
class KPermCollection:
    '''
    Container for a list of OligoKPerm
    '''
    kperms=[] # type: List[OligoKPerm]

    @initdefaults(frozenset(locals()))
    def __init__(self,**kwa):
        pass

    @classmethod
    def product(cls,*args):
        '''
        returns a KPermCollection with the product of kperms in first
        and kperms in second
        '''
        if len(args)==1:
            return args[0]

        #res = cls.__product2(*args[:2])
        res = cls.__product2(args[0],args[1])
        for kpc in args[2:]:
            res = cls.__product2(res,kpc)
        return res

    @classmethod
    def __product2(cls,first,second):
        '''
        takes the product of 2 elements at a time
        '''
        kperms = list(OligoKPerm.add(*prd)
                      for prd in itertools.product(first.kperms,second.kperms))
        return cls(kperms=kperms)


    def intersect_with(self,other):
        '''
        returns True if any OligoKPerm is shared by the 2 collections
        REMINDER: 2 groups intersecting (i.e. which share the same oligos)
        both contain the kperm related to the intersecting oligos.
        So one has to consider only 1 of the 2 intersecting subgroups.
        '''
        for kpr in self.kperms:
            if any(set(kpr.kperm).intersection(set(oth.kperm)) for oth in other.kperms):
                return True
        return False
