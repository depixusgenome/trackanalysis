#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extracts information from a report
"""
from typing                 import Optional, Sequence, Tuple, cast
from openpyxl               import load_workbook
from excelreports.creation  import writecolumns

def _id(row, ibead):
    val = row[ibead].value
    if val is None:
        return
    elif isinstance(val, str):
        try:
            return int(val.split('B')[-1])
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
            beadid = int(val.split('B')[-1])
        except ValueError:
            return
    else:
        try:
            beadid = int(val)
        except ValueError:
            return

    info.setdefault(ref, []).append(beadid)

def _read_params(rows):
    ids   = [None, None, None] # type: List[Optional[int]]
    names = (u'bead', u'stretch', u'bias')
    for row in rows:
        for i, cell in enumerate(row):
            try:
                ids[names.index(str(cell.value).lower())] = i
            except ValueError:
                pass
        if ids.count(None) != 3:
            break

    info = list() # type: List[Tuple[int,float,float]]
    if ids.count(None) == 0:
        cnv = (_id, _tofloat, _tofloat)
        for row in rows:
            vals = tuple(cnv[i](row, ids[i]) for i in range(len(names)))
            if None not in vals:
                info.append(vals)

    return info

def _read_summary(rows):
    info  = dict() # type: Dict[str,List[int]]
    ibead = cast(Optional[int], None)
    iref  = cast(Optional[int], None)
    for row in rows:
        for i, cell in enumerate(row):
            if str(cell.value).lower() == u"bead":
                ibead = i
            elif str(cell.value).lower() == u"reference":
                iref = i
        if ibead is not None and iref is not None:
            break

    if ibead is not None and iref is not None:
        for row in rows:
            _add(info, row, ibead, row[iref].value.strip())
    return info

def _read_identifications(rows):
    info = dict() # type: Dict[str,List[int]]
    inds = []     # type: Sequence[Tuple[int,str]]
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

    return info

def read(fname:str) -> Sequence[Tuple[str,Sequence[int]]]:
    u"extracts bead ids and their reference from a report"
    wbook = load_workbook(filename=fname, read_only=True)
    info  = dict() # type: Dict[str,List[int]]
    for sheetname in wbook.get_sheet_names():
        if sheetname.lower() == "summary":
            info = _read_summary(iter(wbook[sheetname].rows))
            break

        elif sheetname.lower() == "identification":
            info = _read_identifications(iter(wbook[sheetname].rows))

    return tuple((x,tuple(y)) for x, y in info.items())

def readparams(fname:str) -> Sequence[Tuple[int,Sequence[int]]]:
    u"extracts bead ids and their reference from a report"
    wbook = load_workbook(filename=fname, read_only=True)
    for sheetname in wbook.get_sheet_names():
        if sheetname.lower() == "summary":
            return _read_params(iter(wbook[sheetname].rows))

        elif sheetname.lower() == "identification":
            return tuple()

def write(fname:str, items: Sequence[Tuple[str,Sequence[int]]]):
    u"write bead ids and their reference to a report"
    writecolumns(fname, u"Identification", items)
