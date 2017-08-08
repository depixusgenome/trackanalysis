#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'subclass networkx DiGraph for assembling'

from typing import Generator
import networkx

# # copy of these graphs is too long
# class PermGraph(networkx.DiGraph):
#     '''
#     subclassing for assembling
#     could eventually replace Partition
#     probably replace most of the class by Tuple manipulation
#     '''

#     def __init__(self,**kwa):
#         perms=kwa.get("perms",[]) # type: List[data.OligoPerm]
#         if "perms" in kwa:
#             del kwa["perms"]
#         super().__init__(**kwa)
#         for prmid,prm in enumerate(perms[1:]):
#             self.add_edge(perms[prmid],prm)

#         # self starts may not be needed (we know kperms with index.span.instersection([0]))
#         self.starts=frozenset([perms[0]]) if perms else frozenset([])
#         self.last=perms[-1] if perms else None

#     def append(self,perm):
#         'add to the graph and creates edges with last'
#         if not self.starts:
#             self.add_node(perm)
#             self.starts=self.starts.union(frozenset([perm]))
#             self.last=perm
#         else:
#             self.add_edge(self.last,perm)
#             self.last=perm

#     def __add2(self,other):
#         'add edges and nodes from other into self'
#         self.starts=self.starts.union(frozenset(other.starts))
#         for edge in other.edges():
#             self.add_edge(*edge)

#     def add(self,*args):
#         'takes graphs and combine them with self'
#         pgraph=self.copy()
#         for pgr in args:
#             pgraph.__add2(pgr) # pylint: disable=protected-access

#         return pgraph

#     def paths(self)->Generator:
#         'generates all list of perms from start to last'
#         for start in self.starts:
#             for path in networkx.all_simple_paths(self,start,self.last):
#                 yield path

#     def __copy__(self):
#         'must override copy from networkx which calls deepcopy'
#         newgraph=type(self)()
#         newgraph.add_edges_from(self.edges())
#         newgraph.starts=self.starts
#         newgraph.last=self.last
#         return newgraph

#     def copy(self):
#         return self.__copy__()



class PermGraph:
    '''
    subclassing for assembling
    could eventually replace Partition
    probably replace most of the class by Tuple manipulation
    '''

    def __init__(self,**kwa):
        perms=kwa.get("perms",[]) # type: List[data.OligoPerm]
        self.edges=[] # type: List[Tuple[data.OligoPerm,data.OligoPerm]]
        if perms:
            self.edges=[(perms[prmid],prm) for prmid,prm in enumerate(perms[1:])]

        # self starts may not be needed (we know kperms with index.span.instersection([0]))
        self.starts=frozenset([perms[0]]) if perms else frozenset([])
        self.last=perms[-1] if perms else None

    def append(self,perm):
        'add to the graph and creates edges with last'
        if not self.starts:
            self.starts=self.starts.union(frozenset([perm]))
            self.last=perm
        else:
            self.edges.append((self.last,perm))
            self.last=perm

    def __add2(self,other):
        'add edges and nodes from other into self'
        self.starts=self.starts.union(frozenset(other.starts))
        self.edges.extend(other.edges)

    def add(self,*args):
        'takes graphs and combine them with self'
        pgraph=self.copy()
        for pgr in args:
            pgraph.__add2(pgr) # pylint: disable=protected-access

        return pgraph

    def paths(self)->Generator:
        'generates all list of perms from start to last'
        graph=networkx.DiGraph()
        graph.add_edges_from(self.edges)
        # create a Graph
        for start in self.starts:
            for path in networkx.all_simple_paths(graph,start,self.last):
                yield path

    def __copy__(self):
        '''
        copies necessary data
        data.OligoPerm are never changed
        copying address instead
        '''
        cpy=type(self)()
        cpy.edges=list(self.edges)
        cpy.starts=frozenset(self.starts)
        cpy.last=self.last
        return cpy

    def copy(self):
        'calls __copy__'
        return self.__copy__()
