#!/usr/bin/env python3
# -*- coding: utf-8 -*-    

'subclass networkx DiGraph for assembling'

import networkx


class PermGraph(networkx.DiGraph):
    'subclassing for assebmling'
    def __init__(self,**kwa):
        perms=kwa.get("perms",[])
        if "perms" in kwa:
            del kwa["perms"]
        super(PermGraph,self).__init__(**kwa)
        for prmid,prm in enumerate(perms[1:]):
            self.add_edge(perms[prmid],prm)

        self.last=perms[-1]

    def append(self,perm):
        'add to the graph and creates edges with last'
        self.add_node(perm)
        self.add_edge(self.last,perm)
        self.last=perm

    def merge(self,other):
        'add edges and nodes from other into self'
        for edge in other.edges():
            self.add_edge(*edge)

    def merge_to(self,*args):
        'takes graphs and combine them with self'
        pgraph=self.copy()
        for pgr in args:
            pgraph.merge(pgr)

        return pgraph

    def __copy__(self,**kwa):
        mod=dict(list(self.__dict__.items())+list(kwa.items()))
        return PermGraph(**mod)

    def copy(self,*args,**kwa):
        'calls copy'
        return self.__copy__(**kwa)

