#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extracts information from a report
"""
from typing                 import (Optional,   # pylint: disable=unused-import
                                    Sequence, Tuple, List, Union,
                                    Dict, Callable, cast)
from pathlib                import Path
from openpyxl               import load_workbook
from excelreports.creation  import writecolumns

def _id(row, ibead):
    val = row[ibead].value
    if val is None:
        return

    if isinstance(val, str):
        try:
            return int(val.split('B')[-1]) if 'B' in val else int(val)
        except ValueError:
            return

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

    if isinstance(val, str):
        try:
            return int(val.split('B')[-1]) if 'B' in val else int(val)
        except ValueError:
            return

    try:
        beadid = int(val)
    except ValueError:
        return

    info.setdefault(ref, []).append(beadid)

def _read_summary(rows) -> List[Tuple[int, str, Optional[float], Optional[float]]]:
    ids   = [None, None, None, None] # type: List[Optional[int]]
    names = ('bead', 'reference', 'stretch', 'bias')
    for row in rows:
        for i, cell in enumerate(row):
            try:
                ids[names.index(str(cell.value).lower())] = i
            except ValueError:
                pass
        if ids.count(None) != 4:
            break

    info = list() # type: List[Tuple[int,str,float,float]]
    if ids.count(None) == 0:
        cnv = (_id, lambda r, i: str(r[i].value), _tofloat, _tofloat) # type: Sequence[Callable]
        for row in rows:
            vals = tuple(fcn(row, idx) for fcn, idx in zip(cnv, ids))
            if None not in vals[:2]:
                info.append(cast(Tuple[int, str, Optional[float], Optional[float]], vals))
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

def readparams(fname:str) -> Union[List[Tuple[int,str,Optional[float],Optional[float]]],
                                   List[Tuple[int,str]]]:
    "extracts bead ids and their reference from a report"
    if not Path(fname).exists():
        raise ValueError("Id file path unreachable","warning")
    if Path(fname).is_dir():
        raise ValueError("Id file path is a directory", "warning")
    wbook = load_workbook(filename=fname, read_only=True)
    for sheetname in wbook.sheetnames:
        if sheetname.lower() == "summary":
            return _read_summary(iter(wbook[sheetname].rows))

        elif sheetname.lower() == "identification":
            return _read_identifications(iter(wbook[sheetname].rows))
    res = [] # type: List[Tuple[int, str]]
    return res

def writeparams(fname:str, items: Sequence[Tuple[str,Sequence[int]]]):
    "write bead ids and their reference to a report"
    writecolumns(fname, "Identification", items)
