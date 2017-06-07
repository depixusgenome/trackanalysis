#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Creates excel of csv files for reporting any type of data"
from typing                 import (Sequence, Iterator, Union, TypeVar,
                                    Callable, Optional, cast, IO)
from pathlib                import Path
from contextlib             import closing, contextmanager
from abc                    import ABCMeta, abstractmethod
from inspect                import getmembers
from xlsxwriter             import Workbook
from xlsxwriter.chart       import Chart

Column    = TypeVar('Column', bound = Callable)
Columns   = Sequence[Column]

_CNAME    = 'column_name'
_CCOMMENT = 'column_comment'
_CORDER   = 'column_order'
_CUNITS   = 'column_units'
_CEXCLUDE = 'column_exclude'
_CCOND    = 'column_cond'
_CFMT     = 'column_fmt'
class _ColumnMethod(object):
    def __init__(self):
        self._index = 0

    def __call__(self, name: str, other = None, **kwargs):
        ind          = self._index+1
        self._index += 1

        def _deco(fcn_):
            fcn = getattr(fcn_, '__func__', fcn_)
            setattr(fcn, _CNAME,    name)
            setattr(fcn, _CCOMMENT, fcn.__doc__)
            setattr(fcn, _CUNITS,   kwargs.get('units', None))
            setattr(fcn, _CORDER,   ind)
            setattr(fcn, _CCOND,    kwargs.get('cond', None))
            setattr(fcn, _CFMT,     kwargs.get('fmt',  None))

            exclude = kwargs.get('exclude', None)
            if exclude is None:
                setattr(fcn, _CEXCLUDE, lambda _: False)
            else:
                setattr(fcn, _CEXCLUDE, exclude)
            return fcn

        if other is not None:
            return _deco(other)
        return _deco

def column_method(name:str, other = None, _functor = _ColumnMethod(), **kwargs):
    u"decorator for signaling that a method is responsible for a column of data"
    return _functor(name, other, **kwargs)

def sheet_class(name: str, other = None, **kwargs):
    u"Defines the method as a column"
    def _deco(fcn):
        fcn.sheet_name = name
        for title, value in kwargs.items():
            setattr(fcn, title, value)
        return fcn

    if other is not None:
        return _deco(other)
    return _deco

class _BaseReporter(metaclass=ABCMeta):
    def comments(self, fcn: Callable[['_BaseReporter'], str]) -> Optional[str]:
        u"returns column comments"
        comments = getattr(fcn, _CCOMMENT, None)
        if callable(comments):
            comments = cast(str, comments(self))

        units    = getattr(fcn, _CUNITS,   None)
        if callable(units):
            units = cast(str, units(self))

        if units is None and comments is None:
            return None
        if comments is None:
            return u'Units: '+units
        if units is None:
            return comments
        return comments+u'\nUnits: '+units

    @staticmethod
    def columnname(col: Column):
        u"returns attribute _CNAME or None"
        return getattr(col, _CNAME, None)

    def columns(self) -> Columns:
        u"list of columns in table"
        tmp  = iter(obj for _, obj in getmembers(self) if hasattr(obj, _CNAME))
        tmp  = iter(obj for obj in tmp if not getattr(obj, _CEXCLUDE, lambda _: False)(self))
        cols = cast(Columns, list(tmp))
        return sorted(cols, key = lambda x: getattr(x, _CORDER, None))

    def columnindex(self, *elems) -> Iterator[int]:
        u"returns a column index"
        tmp   = iter(obj for _, obj in getmembers(self) if hasattr(obj, _CNAME))
        tmp   = iter(obj for obj in tmp if not getattr(obj, _CEXCLUDE, lambda _: False)(self))
        cols  = sorted(list(tmp), key = lambda x: getattr(x, _CORDER, None))
        names = '__name__', _CNAME
        for elem in elems:
            for i, col in enumerate(cols):
                if any(getattr(col, name, None) == elem for name in names):
                    yield i

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"

    @abstractmethod
    def header(self, data:Sequence):
        u"creates the header"

    @abstractmethod
    def table(self):
        u"creates the table"

class CsvReporter(_BaseReporter):
    u"All generic methods for creating a CSV report"
    _TEXT_HEADER     = '#### '
    _TEXT_FORMAT     = '{: <16}\t'
    _TEXT_SEPARATOR  = '\t'
    _TABLE_FORMAT    = '{: <16};\t'
    _TABLE_SEPARATOR = ';\t'
    def __init__(self, filename):
        if not hasattr(self, 'sheet_name'):
            self.sheet_name = None                     # type: Optional[str]
        if isinstance(filename, CsvReporter):
            self.book      = filename.book
            self._tablerow = getattr(filename, '_tablerow', 0)  # type: int
        else:
            self.book      = filename
            self._tablerow = 0
        self.sheet = self.sheet_name # type: Union[Worksheet,str]

    def _printtext(self, *args):
        args = tuple('' if x is None else x for x in args)
        args = (self._TEXT_FORMAT*len(args)).format(*args).strip()
        print(self._TEXT_HEADER, args, sep = self._TEXT_SEPARATOR, file = self.book)

    def _printline(self, *args):
        args = tuple('' if x is None else x for x in args)
        args = (self._TABLE_FORMAT*len(args)).format(*args).strip()
        print(args, sep = self._TABLE_SEPARATOR, file = self.book)

    def header(self, data:Sequence):
        u"creates the header"
        self._printtext('')
        for line in data:
            self._printtext(*line)
        self._printtext()

    def table(self):
        u"creates the table"
        def _title(fcn):
            return getattr(fcn, _CNAME, '')

        def _doc(fcn):
            comment = self.comments(fcn)
            if comment is None:
                return None
            comment = comment.strip(' \n')
            return comment.replace('\n', '\n'+self._TEXT_HEADER+'\t\t\t')

        txt     = self.columns()
        header  = [('TABLE: ', self.sheet)]
        header += [(_title(fcn)+":", _doc(fcn)) for fcn in txt]
        self.header(header)
        self._printline(*(_title(fcn) for fcn in txt))

        for line in self.iterate():
            values = tuple(fcn(*line) for fcn in txt)
            self._printline(*values)
        self._printline()

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"

class XlsReporter(_BaseReporter):
    u"All generic methods for creating an XLS report"
    _INT_FMT  = "0"
    _REAL_FMT = "0.00"
    def __init__(self, arg):
        if isinstance(arg, XlsReporter):
            rep            = cast(XlsReporter, arg)
            self.book      = rep.book                      # type: Workbook
            self.fmt       = rep.fmt
            self._tablerow = getattr(rep, '_tablerow', 0)  # type: int
        else:
            self.book = arg                                # type: Workbook

            marked    = dict(bg_color = 'gray')
            self.fmt  = {'marked'       : self.book.add_format(marked),
                         self._INT_FMT : self.book.add_format(marked),
                         self._REAL_FMT: self.book.add_format(marked),
                         'real'        : self.book.add_format(),
                         'int'         : self.book.add_format()}
            self.fmt['real']        .set_num_format(self._REAL_FMT)
            self.fmt[self._REAL_FMT].set_num_format(self._REAL_FMT)
            self.fmt['int']         .set_num_format(self._INT_FMT)
            self.fmt[self._INT_FMT ].set_num_format(self._INT_FMT)
            self._tablerow = 0

        if not hasattr(self, 'sheet_name'):
            self.sheet_name = None                     # type: Optional[str]

        if self.sheet_name in self.book.sheetnames:
            self.sheet = self.book.get_worksheet_by_name(self.sheet_name)
        else:
            self.sheet = self.book.add_worksheet(self.sheet_name)

    def header(self, data:Sequence):
        u"creates the header"
        for irow, line in enumerate(data):
            for icol, cell in enumerate(line):
                self.sheet.write(irow, icol, cell)

    def _getfmt(self, mark:bool, fmt):
        return fmt if not mark else self.fmt[getattr(fmt, 'num_format', 'marked')]

    def table(self):
        u"creates the table"
        def _write_titles():
            for i, fcn in enumerate(self.columns()):
                comment = self.comments(fcn)
                if comment is not None:
                    self.sheet.write_comment(self.tablerow(), i, comment.strip(),
                                             dict(visible = False))

                result = getattr(fcn, _CNAME, None)
                if result is not None:
                    self.sheet.write(self.tablerow(), i, result)

        def _write_data():
            def _get(fcn):
                fmt = getattr(fcn, _CFMT, None)
                if callable(fmt) and not isinstance(fmt, type):
                    fmt = fmt(self)

                if isinstance(fmt, str):
                    return getattr(self, fmt, None)

                if fmt is None:
                    ret = fcn.__annotations__.get('return')
                elif isinstance(fmt, type):
                    ret = fmt

                if ret is float or ret == Union[float, ret]:
                    return self.fmt['real']
                if ret is int or ret == Union[int, ret]:
                    return self.fmt['int']
                return fmt

            fcns = tuple((*i, _get(i[1])) for i in enumerate(self.columns()))

            for i, line in enumerate(self.iterate()):
                irow = self.tablerow() + i + 1
                mark = self.linemark(line)
                for j, fcn, fmt in fcns:
                    result = fcn(*line)

                    if isinstance(result, Chart):
                        self.sheet.insert_chart(irow, j, result)
                    else:
                        self.sheet.write(irow, j, result, self._getfmt(mark, fmt))

            return irow


        def _write_cond(irow: int):
            for i, fcn in enumerate(self.columns()):
                cond = getattr(fcn, _CCOND, None)
                if cond is None:
                    continue
                if callable(cond):
                    cond = cond(self)
                if isinstance(cond, dict):
                    cond = (cond,)
                for one in cond:
                    self.sheet.conditional_format(self.tablerow()+1, i, irow, i, one)

        _write_titles()
        irow = _write_data()
        _write_cond(irow)

    def tablerow(self):
        u"start row of the table"
        return self._tablerow

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"

    @staticmethod
    def linemark(_) -> bool:
        u"returns a function returning an optional line format"
        return False

class Reporter(XlsReporter, CsvReporter):
    u"Model independant class"
    def __init__(self, arg):
        if isinstance(arg, Workbook) or (isinstance(arg, Reporter) and arg.isxlsx()):
            XlsReporter.__init__(self, arg)
        else:
            CsvReporter.__init__(self, arg)

    def isxlsx(self):
        u"whether the file is an xls file or not"
        return isinstance(self.book, Workbook)

    def header(self, data:Sequence):
        u"creates header"
        if self.isxlsx():
            XlsReporter.header(self, data)
        else:
            CsvReporter.header(self, data)
        self._tablerow += len(data)+1

    def table(self):
        u"creates table"
        if self.isxlsx():
            XlsReporter.table(self)
        else:
            CsvReporter.table(self)

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"

FILENAME = Union[Path, str]
FILEOBJ  = Union[IO,Workbook]
@contextmanager
def fileobj(fname:FILENAME) -> Iterator[FILEOBJ]:
    u"Context manager for opening xlsx or text file"
    if Path(str(fname)).suffix in ('.xlsx', '.xls'):
        with closing(Workbook(str(fname))) as book:
            yield book
    else:
        with open(str(fname), 'w', encoding = 'utf-8') as stream:
            yield stream

def writecolumns(filename, sheetname, items):
    u"Writes columns to an excel/csv file"

    def _get(lst):
        return lambda i: lst[i] if len(lst) > i else None

    cols = list(column_method(name)(_get(lst)) for name, lst in items)

    def iterate(_):
        u"Iterates through sheet's base objects and their hierarchy"
        for i in range(max(len(lst) for _, lst in items)):
            yield (i,)

    def columns(_):
        u"list of columns in table"
        return cols

    sheet = type("Sheet", (Reporter,),
                 dict(iterate    = iterate,
                      columns    = columns,
                      sheet_name = sheetname))

    with fileobj(filename) as book:
        sheet(book).table() # pylint: disable=abstract-class-instantiated
