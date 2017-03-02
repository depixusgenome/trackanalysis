#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extracts information from a report
"""
from typing                 import (Optional,   # pylint: disable=unused-import
                                    Sequence, Tuple, List, Union, Callable, cast)
from openpyxl               import load_workbook
from excelreports.creation  import writecolumns

def _id(row, ibead):
    val = row[ibead].value
    if val is None:
        return
    elif isinstance(val, str):
        try:
            if 'B' in val:
                return int(val.split('B')[-1])
            else:
                return int(val)
        except ValueError:
            return
    else:
        try:
            return int(val)
        except ValueError:
            return

def _tofloat(row, ibead):
    val = row[ibead].value
    if val is not None:
        try:
            return float(val)
        except ValueError:
            pass

def _add(info, row, ibead, ref):
    val = row[ibead].value
    if val is None:
        return
    elif isinstance(val, str):
        try:
            if 'B' in val:
                return int(val.split('B')[-1])
            else:
                return int(val)
        except ValueError:
            return
    else:
        try:
            beadid = int(val)
        except ValueError:
            return

    info.setdefault(ref, []).append(beadid)

def _read_summary(rows) -> List[Tuple[int, str, float, float]]:
    ids   = [None, None, None, None] # type: List[Optional[int]]
    names = (u'bead', u'reference', u'stretch', u'bias')
    for row in rows:
        for i, cell in enumerate(row):
            try:
                ids[names.index(str(cell.value).lower())] = i
            except ValueError:
                pass
        if ids.count(None) != 3:
            break

    info = list() # type: List[Tuple[int,str,float,float]]
    if ids.count(None) == 0:
        cnv = (_id, str, _tofloat, _tofloat) # type: Sequence[Callable]
        for row in rows:
            vals = tuple(fcn(row, idx) for fcn, idx in zip(cnv, ids))
            if None not in vals:
                info.append(cast(Tuple[int,str,float,float], vals))

    return info

def _read_identifications(rows) -> List[Tuple[int,str]]:
    info = dict() # type: Dict[str,List[int]]
    inds = []     # type: List[Tuple[int,str]]
    for row in rows:
        for i, cell in enumerate(row):
            val = str(cell.value)
            if val != "":
                inds.append((i, val))
        if len(inds):
            break

    for row in rows:
        for ibead, ref in inds:
            _add(info, row, ibead, ref)

    res = [] # type: List[Tuple[int,str]]
    for hpin, beads in info.items():
        res.extend((i,hpin) for i in beads)
    return res

def readparams(fname:str) -> Union[List[Tuple[int,str,float,float]],
                                   List[Tuple[int,str]]]:
    u"extracts bead ids and their reference from a report"
    wbook = load_workbook(filename=fname, read_only=True)
    for sheetname in wbook.get_sheet_names():
        if sheetname.lower() == "summary":
            return _read_summary(iter(wbook[sheetname].rows))

        elif sheetname.lower() == "identification":
            return _read_identifications(iter(wbook[sheetname].rows))

def write(fname:str, items: Sequence[Tuple[str,Sequence[int]]]):
    u"write bead ids and their reference to a report"
    writecolumns(fname, u"Identification", items)
