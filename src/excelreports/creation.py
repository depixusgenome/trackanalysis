#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates excel of csv files for reporting any type of data"
from typing                 import (Sequence, Iterator, Union, TypeVar,
                                    Callable, Iterable, Optional, cast, IO)
from pathlib                import Path
from contextlib             import closing, contextmanager
from abc                    import ABCMeta, abstractmethod
from inspect                import getmembers
from xlsxwriter             import Workbook
from xlsxwriter.worksheet   import Worksheet
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
class _ColumnMethod:
    def __init__(self):
        self._index = 0

    _NAMES = dict(name    = (_CNAME,    lambda _: None),
                  doc     = (_CCOMMENT, lambda i: i.__doc__),
                  index   = (_CORDER,   lambda _: None),
                  units   = (_CUNITS,   lambda _: None),
                  cond    = (_CCOND,    lambda _: None),
                  fmt     = (_CFMT,     lambda _: None),
                  exclude = (_CEXCLUDE, lambda _: (lambda _: False)))

    def __call__(self, name: Union[type, str], other = None, **items):
        self._index   += 1
        items['name']  = name
        items['index'] = self._index+1
        def _deco(fcn_):
            kwargs = dict(items)
            fcn    = getattr(fcn_, '__func__', fcn_)
            if isinstance(name, type):
                old = getattr(name, fcn.__name__)
                old = getattr(old, '__func__', old)
                kwargs.pop('name')
                for i, (j,_) in self._NAMES.items():
                    kwargs.setdefault(i, getattr(old, j))

            for i, (j, k) in self._NAMES.items():
                setattr(fcn, j, kwargs[i] if i in kwargs else k(fcn))
            return fcn

        if other is not None:
            return _deco(other)
        return _deco

def column_method(name: Union[type, str], other = None, _functor = _ColumnMethod(), **kwargs):
    "decorator for signaling that a method is responsible for a column of data"
    return _functor(name, other, **kwargs)

def sheet_class(name: str, other = None, **kwargs):
    "Defines the method as a column"
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
        "returns column comments"
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
        "returns attribute _CNAME or None"
        return getattr(col, _CNAME, None)

    def columns(self) -> Columns:
        "list of columns in table"
        tmp  = iter(obj for _, obj in getmembers(self) if hasattr(obj, _CNAME))
        tmp  = iter(obj for obj in tmp if not getattr(obj, _CEXCLUDE, lambda _: False)(self))
        cols = cast(Columns, list(tmp))
        return sorted(cols, key = lambda x: getattr(x, _CORDER, None))

    def columnindex(self, *elems) -> Iterator[int]:
        "returns a column index"
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
        "Iterates through sheet's base objects and their hierarchy"

    @abstractmethod
    def header(self, data:Sequence):
        "creates the header"

    @abstractmethod
    def table(
            self,
            columns : Optional[Iterable] = None,
            rows    : Optional[Iterable] = None,
            start   : Optional[int]      = None
    ):
        "creates the table"

class CsvReporter(_BaseReporter):
    "All generic methods for creating a CSV report"
    _TEXT_HEADER     = '#### '
    _TEXT_FORMAT     = '{: <16}\t'
    _TEXT_SEPARATOR  = '\t'
    _TABLE_FORMAT    = '{: <16};\t'
    _TABLE_SEPARATOR = ';\t'
    book:  Union[IO, Workbook]
    sheet: Union[Worksheet,str]
    def __init__(self, filename):
        if not hasattr(self, 'sheet_name'):
            self.sheet_name: Optional[str] = None
        if isinstance(filename, CsvReporter):
            self.book           = filename.book
            self._tablerow: int = getattr(filename, '_tablerow', 0)
        else:
            self.book      = filename
            self._tablerow = 0
        self.sheet         = self.sheet_name

    def _printtext(self, *args):
        args = tuple('' if x is None else x for x in args)
        args = (self._TEXT_FORMAT*len(args)).format(*args).strip()
        print(self._TEXT_HEADER, args, sep = self._TEXT_SEPARATOR, file = self.book)

    def _printline(self, *args):
        args = tuple('' if x is None else x for x in args)
        args = (self._TABLE_FORMAT*len(args)).format(*args).strip()
        print(args, sep = self._TABLE_SEPARATOR, file = self.book)

    def header(self, data:Sequence):
        "creates the header"
        self._printtext('')
        for line in data:
            self._printtext(*line)
        self._printtext()

    def table(
            self,
            columns : Optional[Iterable] = None,
            rows    : Optional[Iterable] = None,
            start   : Optional[int]      = None
    ):
        "creates the table"
        def _title(fcn):
            return getattr(fcn, _CNAME, '')

        def _doc(fcn):
            comment = self.comments(fcn)
            if comment is None:
                return None
            comment = comment.strip(' \n')
            return comment.replace('\n', '\n'+self._TEXT_HEADER+'\t\t\t')

        txt     = list(self.columns() if columns is None else columns)
        header  = [('TABLE: ', self.sheet)]
        header += [(_title(fcn)+":", _doc(fcn)) for fcn in txt]
        self.header(header)
        self._printline(*(_title(fcn) for fcn in txt))

        for line in self.iterate() if rows is None else rows:
            values = tuple(fcn(*line) for fcn in txt)
            self._printline(*values)
        self._printline()

    @abstractmethod
    def iterate(self):
        "Iterates through sheet's base objects and their hierarchy"

class XlsReporter(_BaseReporter):
    "All generic methods for creating an XLS report"
    _INT_FMT  = "0"
    _REAL_FMT = "0.00"
    _MARKED   = dict(bg_color='gray')
    book:  Union[IO, Workbook]
    sheet: Union[Worksheet, str]
    def __init__(self, arg):
        if isinstance(arg, XlsReporter):
            rep            = cast(XlsReporter, arg)
            self.book      = rep.book                      # type: Workbook
            self.fmt: str  = rep.fmt
            self._tablerow = getattr(rep, '_tablerow', 0)  # type: int
        else:
            self.book = arg                                # type: Workbook

            self.fmt  = {'marked'       : self.book.add_format(self._MARKED),
                         self._INT_FMT : self.book.add_format(self._MARKED),
                         self._REAL_FMT: self.book.add_format(self._MARKED),
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
        "creates the header"
        irow = 0
        for irow, line in enumerate(data):
            for icol, cell in enumerate(line):
                cast(Worksheet, self.sheet).write(irow, icol, cell)
        self._tablerow += irow+2

    def _getfmt(self, mark:bool, fmt):
        return fmt if not mark else self.fmt[getattr(fmt, 'num_format', 'marked')]

    def table(
            self,
            columns : Optional[Iterable] = None,
            rows    : Optional[Iterable] = None,
            start   : Optional[int]      = None
    ):
        "creates the table"
        istart = self.tablerow() if start is None else start
        cols:  Callable = self.columns
        lines: Callable = self.iterate
        if columns is not None:
            columns = list(columns)
            cols    = lambda: iter(cast(Iterable, columns))
        if rows is not None:
            rows  = list(rows)
            lines = lambda: iter(cast(Iterable, rows))

        self.__write_titles(istart, cols())
        irow = self.__write_data(istart, cols(), lines())
        self.__write_cond(istart, cols(), irow)
        self._tablerow = irow+2

    def __write_titles(self, start: int, columns):
        sheet = cast(Worksheet, self.sheet)
        for i, fcn in enumerate(columns):
            comment = self.comments(fcn)
            if comment is not None:
                sheet.write_comment(start, i, comment.strip(), dict(visible = False))

            result = getattr(fcn, _CNAME, None)
            if result is not None:
                sheet.write(start, i, result)

    def __write_data(self, start: int, columns, lines):
        fcns  = tuple((*i, self.__format(i[1])) for i in enumerate(columns))
        sheet = cast(Worksheet, self.sheet)
        irow  = 1
        for i, line in enumerate(lines):
            irow = start + i + 1
            mark = self.linemark(line)
            for j, fcn, fmt in fcns:
                result = fcn(*line)

                if isinstance(result, Chart):
                    sheet.insert_chart(irow, j, result)
                else:
                    sheet.write(irow, j, result, self._getfmt(mark, fmt))

        return irow

    def __write_cond(self, start:int, columns, irow: int):
        sheet = cast(Worksheet, self.sheet)
        for i, fcn in enumerate(columns):
            cond = getattr(fcn, _CCOND, None)
            if cond is None:
                continue
            if callable(cond):
                cond = cond(self)
            if isinstance(cond, dict):
                cond = (cond,)
            for one in cond:
                sheet.conditional_format(start+1, i, irow, i, one)


    def tablerow(self):
        "start row of the table"
        return self._tablerow

    @abstractmethod
    def iterate(self):
        "Iterates through sheet's base objects and their hierarchy"

    @staticmethod
    def linemark(_) -> bool:
        "returns a function returning an optional line format"
        return False

    def __format(self, fcn):
        fmt = getattr(fcn, _CFMT, None)
        if callable(fmt) and not isinstance(fmt, type):
            fmt = fmt(self)

        if isinstance(fmt, str):
            res = self.fmt.get('s'+fmt, None)
            if res is None:
                self.fmt['s'+fmt] = self.book.add_format()
                self.fmt[fmt]     = self.book.add_format(self._MARKED)
                self.fmt['s'+fmt].set_num_format(fmt)
                self.fmt[fmt]    .set_num_format(fmt)
                return self.fmt['s'+fmt]
            return res

        if fmt is None:
            ret = fcn.__annotations__.get('return')
        elif isinstance(fmt, type):
            ret = fmt

        if ret is float or ret == Union[float, ret]:
            return self.fmt['real']
        if ret is int or ret == Union[int, ret]:
            return self.fmt['int']
        return fmt


class Reporter(XlsReporter, CsvReporter):
    "Model independant class"
    def __init__(self, arg):
        if isinstance(arg, Workbook) or (isinstance(arg, Reporter) and arg.isxlsx()):
            XlsReporter.__init__(self, arg)
        else:
            CsvReporter.__init__(self, arg)

    def isxlsx(self):
        "whether the file is an xls file or not"
        return isinstance(self.book, Workbook)

    def header(self, data:Sequence):
        "creates header"
        if self.isxlsx():
            XlsReporter.header(self, data)
        else:
            CsvReporter.header(self, data)

    def table(
            self,
            columns : Optional[Iterable] = None,
            rows    : Optional[Iterable] = None,
            start   : Optional[int]      = None
    ):
        "creates table"
        if self.isxlsx():
            XlsReporter.table(self, columns, rows, start)
        else:
            CsvReporter.table(self, columns, rows)

    @abstractmethod
    def iterate(self):
        "Iterates through sheet's base objects and their hierarchy"

FILENAME = Union[Path, str]
FILEOBJ  = Union[IO,Workbook]
@contextmanager
def fileobj(fname:FILENAME) -> Iterator[FILEOBJ]:
    "Context manager for opening xlsx or text file"
    if Path(str(fname)).suffix in ('.xlsx', '.xls'):
        with closing(Workbook(str(fname), {'nan_inf_to_errors': True})) as book:
            yield book
    else:
        with open(str(fname), 'w', encoding = 'utf-8') as stream:
            yield stream

def writecolumns(filename, sheetname, items):
    "Writes columns to an excel/csv file"

    def _get(lst):
        return lambda i: lst[i] if len(lst) > i else None

    cols = list(column_method(name)(_get(lst)) for name, lst in items)

    def iterate(_):
        "Iterates through sheet's base objects and their hierarchy"
        for i in range(max(len(lst) for _, lst in items)):
            yield (i,)

    def columns(_):
        "list of columns in table"
        return cols

    sheet = type("Sheet", (Reporter,),
                 dict(iterate    = iterate,
                      columns    = columns,
                      sheet_name = sheetname))

    with fileobj(filename) as book:
        sheet(book).table() # pylint: disable=abstract-class-instantiated
