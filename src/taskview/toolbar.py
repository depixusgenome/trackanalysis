#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
import sys
import time
from typing               import Callable, Iterator, Tuple, Any, TYPE_CHECKING
from functools            import partial
from pathlib              import Path

import bokeh.core.properties   as props

from bokeh                import layouts
from bokeh.document       import Document
from bokeh.models         import Widget
from bokeh.io             import curdoc

from taskcontrol.taskio       import TaskIO
from taskcontrol.beadscontrol import DataSelectionBeadController
from utils                    import initdefaults
from utils.gui                import parseints, leastcommonkeys
from utils.logconfig          import getLogger
from view.dialog              import FileDialog, FileDialogTheme
from view.base                import BokehView, threadmethod, spawn
from view.static              import route
LOGS  = getLogger(__name__)

if TYPE_CHECKING:
    from taskmodel import RootTask   # noqa # pylint: disable=unused-import

class BeadToolbarTheme:
    "BeadToolbarTheme"
    name         = "toolbar"
    width        = 1100
    height       = 40
    openlabel    = 'Open'
    savelabel    = 'Save'
    quitlabel    = 'Quit'
    opentitle    = 'Open a track or analysis file'
    savetitle    = 'Save an analysis file'
    placeholder  = '1, 2, ..., bad, ... ?'
    tail         = ', ...'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass


STORAGE = 'open', 'save'


class TrackFileDialog(FileDialog):
    "A file dialog that doesn't open .gr files first"
    def __init__(self, ctrl):
        super().__init__(ctrl, multiple  = 1, storage = STORAGE[0])

        def _defaultpath(ext, bopen):
            assert bopen

            pot = self.storedpaths(ctrl, STORAGE[0], ext)
            if ctrl.display.get("tasks", "roottask", None) is None:
                pot = [i for i in pot if i.suffix != '.gr']
            return self.firstexistingpath(pot)

        self.__store: Callable = self.access[1]
        self.access            = _defaultpath, None

    def setup(self, ctrl, _):
        "sets the document"
        self.filetypes = TaskIO.extensions(ctrl, 'openers')+'|*'
        self.title     = ctrl.theme.get("toolbar", 'opentitle')

    async def run(self, ctrl, doc):
        "runs the dialog"
        paths = await threadmethod(self.open)
        ctrl.display.handle('toolbardialog', args = {'path': paths})
        if paths is not None:
            def _toolbaropen():
                with ctrl.action:
                    self.__store(paths, True)  # pylint: disable=not-callable
                    ctrl.tasks.opentrack(paths)
            doc.add_next_tick_callback(_toolbaropen)

class SaveFileDialog(FileDialog):
    "A file dialog that adds a default save path"
    def __init__(self, ctrl):
        super().__init__(ctrl, storage = STORAGE[1])

        def _defaultpath(ext, bopen):
            assert not bopen
            pot = [i for i in self.storedpaths(ctrl, STORAGE[0], ext) if i.exists()]
            ope = next((i for i in pot if i.suffix not in ('', '.gr')), None)
            if ope is None:
                ope = self.firstexistingpath(pot)

            pot = self.storedpaths(ctrl, STORAGE[1], ext)
            sav = self.firstexistingparent(pot)

            if ope is None:
                return sav

            if sav is None:
                if Path(ope).is_dir():
                    return ope
                sav = Path(ope).with_suffix(ext[0][1])
            else:
                psa = Path(sav)
                if psa.suffix == '':
                    sav = (psa/Path(ope).stem).with_suffix(ext[0][1])
                else:
                    sav = (psa.parent/Path(ope).stem).with_suffix(psa.suffix)

            self.defaultextension = sav.suffix[1:] if sav.suffix != '' else None
            return str(sav)

        self.__store = self.access[1]
        self.access  = _defaultpath, None

    def setup(self, ctrl, _):
        "sets the document"
        self.filetypes = TaskIO.extensions(ctrl, 'savers')
        self.title     = ctrl.theme.get("toolbar", 'savetitle')

    async def run(self, ctrl, doc):
        "runs the dialog"
        paths = await threadmethod(self.save)
        ctrl.display.handle('toolbardialog', args = {'path': paths})
        if paths is not None:
            def _toolbarsave():
                with ctrl.action:
                    self.__store(paths, False)  # pylint: disable=not-callable
                    ctrl.tasks.savetrack(paths)
            doc.add_next_tick_callback(_toolbarsave)

class DpxToolbar(Widget):
    "Toolbar model"
    __css__            = route("view.css", "icons.css", "toolbar.css")
    __implementation__ = 'toolbar.ts'
    __javascript__     = route()
    frozen      = props.Bool(True)
    open        = props.Int(0)
    save        = props.Int(0)
    doc         = props.Int(0)
    quit        = props.Int(0)
    bead        = props.Int(-1)
    discarded   = props.String('')
    accepted    = props.String('')
    currentbead = props.Bool(True)
    currentfile = props.Int(-1)
    delfile     = props.Int(-1)
    filelist    = props.List(props.String)
    seltype     = props.Bool(True)
    message     = props.String('')
    helpmessage = props.String('')
    hasquit     = props.Bool(False)
    hasdoc      = props.Bool(False)

    def __init__(self, **kwa):
        super().__init__(name = 'Main:toolbar', **kwa)

class MessageTheme:
    "Message theme"
    _SIZ    = 'height: 28px; margin-top: 0px;'
    name    = "toolbar.message"
    period  = 50
    width   = 350
    busy    = "Please wait ..."
    types   = dict(normal  = '<p style="%s">{}</p>' % _SIZ,
                   warning = '<p style="%s color:blue;">{}</p>' % _SIZ,
                   error   = '<p style="%s color:red;"> {}</p>' % _SIZ,
                   busy    = u'Please wait ...')
    timeout = dict(normal  = 1.,
                   error   = 50.,
                   warning = 50.)

    del _SIZ
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class MessageDisplay:
    "Message display"
    name    = "message"
    message = ""
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class MessagesView:
    "Everything related to messages"
    def __init__(self, ctrl, **_):
        self._theme        = ctrl.theme.add(MessageTheme(**_))
        self._display      = ctrl.display.add(MessageDisplay(**_))
        self._last:list    = [None, None, self._theme.timeout['normal']]
        self._tbar         = None
        self._doc:Document = None

    def observe(self, ctrl):
        "initializes globals"
        busy  = self._theme.busy, 'normal'

        @ctrl.display.observe
        def _onstartaction(recursive = None, **_):
            if not recursive:
                self._settext(busy)

        @ctrl.display.observe
        def _onstartcomputation(recursive = None, **_):
            if recursive:
                return
            val = self._display.message
            if val is None or (isinstance(val, tuple) and val[1] == 'normal'):
                self._settext(busy)

        @ctrl.display.observe("stopaction", "stopcomputation")
        def _observer(recursive  = None,
                      value      = None,
                      catcherror = None, **_):
            if not recursive and value is not None:
                LOGS.debug('stop')
                ctrl.display.update(self._display, message = value)
                catcherror[0] = getattr(ctrl, 'CATCHERROR', True)

        @ctrl.display.observe
        def _onmessage(old = None, **_):
            if 'message' in old:
                self._settext(self._display.message)

    def addtodoc(self, ctrl, doc, tbar):
        "add to doc"
        self._tbar = tbar
        self._doc  = doc
        self._last = [None, None, self._theme.timeout['normal']]

        def _setmsg():
            if self._last[0] is None:
                return

            if self._last[0] != '':
                self._tbar.message = self._last[0]
                self._last[0] = ''
                self._last[1] = time.time()+self._last[2]

            elif self._last[1] < time.time():
                self._last[0]      = None
                self._tbar.message = ''
                ctrl.display.update(self._display, message = None)
        doc.add_periodic_callback(_setmsg, self._theme.period)

    def _settext(self, text):
        text = getattr(text, 'value', text)
        if text is None:
            return

        templ = self._theme.types
        for exc, tpe in ((RuntimeWarning, 'warning'), (Exception, 'error')):
            if not isinstance(text, exc):
                continue

            args = getattr(text, 'args', tuple())
            args = (
                (args[0],   tpe) if len(args) == 1 else
                (text,      tpe) if len(args) != 2 else
                (str(args), tpe) if args[1] not in templ else
                args
            )
            break
        else:
            args = text

        txt = str(args[0])
        enc = txt.encode("utf-8") if sys.platform != 'linux' else txt
        val = templ[str(args[1])].format(
            txt
            .replace('<', '&lt')
            .replace('>', '&gt')
            .strip()
            .replace('\n', '<br>')
        )
        if args[1] == 'error':
            if isinstance(text, Exception):
                LOGS.exception(text)
            else:
                LOGS.error(enc)
        elif args[1] == 'warning':
            LOGS.warning(enc)

        timeout       = self._theme.timeout
        self._last[0] = val
        self._last[1] = time.time()+timeout.get(args[1], timeout['normal'])
        self._last[2] = timeout.get(args[1], timeout['normal'])
        if curdoc() is self._doc:
            try:
                self._tbar.message = val
                return
            except RuntimeError:
                pass

def _keyinit(ctrl, name:str, key:str):
    "Sets up the controller"
    ctrl.theme.updatedefaults(
        'keystroke', **{f'{name}{i}': f'{key}{i.capitalize()}' for i in ('up', 'down')}
    )

class BeadInput:
    "Spinner for controlling the current bead"
    @staticmethod
    def init(ctrl):
        "Sets up the controller"
        _keyinit(ctrl, 'bead', 'Page')

    @staticmethod
    def setup(ctrl, tbar: DpxToolbar, _):
        "adds items to doc"
        bdctrl = DataSelectionBeadController(ctrl)

        def _chg_cb(attr, old, new):
            with ctrl.action:
                bdctrl.setbead(ctrl, new)
            tbar.bead = bdctrl.bead

        def _chg_cb2(step):
            if bdctrl.bead is not None:
                _chg_cb(None, None, bdctrl.bead+step)

        tbar.on_change('bead', _chg_cb)

        ctrl.display.updatedefaults(
            'keystroke',
            beadup   = lambda: _chg_cb2(1),
            beaddown = lambda: _chg_cb2(-1)
        )

class RejectedBeadsInput:
    "Text dealing with rejected beads"
    @staticmethod
    def init(ctrl):
        "Sets up the controller"
        ctrl.theme.updatedefaults('keystroke', delbead = 'Shift-Delete')

    @staticmethod
    def setup(ctrl, tbar: DpxToolbar, _):
        "sets-up the gui"
        bdctrl = DataSelectionBeadController(ctrl)

        def _ondiscard_currentbead(*_):
            bead = bdctrl.bead
            if bead is None:
                return
            with ctrl.action:
                bdctrl.setdiscarded(ctrl, set(bdctrl.discarded) | {bead})

        def _ondiscard_currentbead_cb(attr, old, value):
            _ondiscard_currentbead()

        def _onaccepted_cb(attr, old, new):
            beads = parseints(new)
            ctrl.display.handle('selectingbeads',
                                args = {"text": new, "accept": True, "beads": beads})
            if not (None in beads or (len(new) and len(beads) == 0)):
                beads = set(bdctrl.allbeads) - beads
                if (not tbar.seltype) and beads != set(bdctrl.discarded):
                    with ctrl.action:
                        bdctrl.setdiscarded(ctrl, beads)
                    return
            _ontasks()

        def _ondiscarded_cb(attr, old, new):
            beads = parseints(new)
            ctrl.display.handle('selectingbeads',
                                args = {"text": new, "accept": False, "beads": beads})
            if not (None in beads or (len(new) and len(beads) == 0)):
                if tbar.seltype and beads != set(bdctrl.discarded):
                    with ctrl.action:
                        bdctrl.setdiscarded(ctrl, beads)
                    return
            _ontasks()

        tbar.on_change('currentbead', _ondiscard_currentbead_cb)
        tbar.on_change('discarded',   _ondiscarded_cb)
        tbar.on_change('accepted',    _onaccepted_cb)

        def _ontasks(**_):
            disc = set(bdctrl.discarded)
            acc  = set(bdctrl.allbeads) - disc
            tbar.update(accepted  = ', '.join(str(i) for i in sorted(acc)),
                        discarded = ', '.join(str(i) for i in sorted(disc)))
        ctrl.tasks.observe("updatetask", "addtask", "removetask", _ontasks)
        ctrl.display.observe("tasks", _ontasks)

        ctrl.display.updatedefaults('keystroke', delbead = _ondiscard_currentbead)

class FileList:
    "Selection of opened files"
    def __init__(self, ctrl):
        self._ctrl: Any = ctrl

    @staticmethod
    def __pathname(ctrl, task):
        if task.key:
            return task.key

        lst = task.path
        cnf = ctrl.theme.model("toolbar")
        if isinstance(lst, (tuple, list)):
            if len(lst) > 1:
                return Path(lst[0]).stem + cnf.tail
            lst = lst[0]
        return Path(lst).stem

    @classmethod
    def get(cls, ctrl) -> Iterator[Tuple[str, 'RootTask']]:
        "returns current roots"
        cnf   = ctrl.theme.model("toolbar")
        lst   = [next(i) for i in getattr(ctrl, 'tasks', ctrl).tasklist(...)]
        names = leastcommonkeys({i: cls.__pathname(ctrl, i) for i in lst}, cnf.tail)
        return ((names[i], i) for i in lst)

    def __call__(self) -> Iterator[Tuple[str, 'RootTask']]:
        "returns current roots"
        return self.get(self._ctrl)

class FileListInput:
    "Selection of opened files"
    @staticmethod
    def init(ctrl):
        "Sets up the controller"
        FileList(ctrl = ctrl)
        _keyinit(ctrl, 'track', 'Shift-Page')

    @staticmethod
    def setup(ctrl, tbar: DpxToolbar, _):
        "sets-up the gui"
        stop = [False]

        @ctrl.tasks.observe("opentrack", "closetrack")
        def _setfilelist(model = None, **_):
            vals  = list(FileList.get(ctrl))
            mdls  = [i for _, i in vals]
            if model[0] in mdls:
                index = mdls.index(model[0])
            else:
                cur   = ctrl.display.get("tasks", "roottask")
                index = mdls.index(cur) if cur in mdls else 0

            try:
                stop[0] = True
                tbar.update(currentfile = index, filelist = [i for i, _ in vals])
            finally:
                stop[0] = False

        def _oncurrentfile_cb(attr, old, new):
            inew = int(new)
            if inew == -1:
                return

            lst = list(FileList.get(ctrl))
            if inew >= len(lst):
                _setfilelist(model = [ctrl.display.get("tasks", "roottask")])
            elif not stop[0]:
                with ctrl.action:
                    ctrl.display.update(
                        "tasks", taskcache = ctrl.tasks.processors(lst[inew][1], copy = False)
                    )
        tbar.on_change('currentfile', _oncurrentfile_cb)

        def _ondelfile_cb(attr, old, new):
            inew = int(new)
            if inew == -1:
                return

            tbar.delfile = -1
            lst          = list(FileList.get(ctrl))
            if 0 <= inew < len(lst):
                with ctrl.action:
                    ctrl.tasks.closetrack(lst[inew][1])

        tbar.on_change('delfile', _ondelfile_cb)

        def _chg_cb2(step):
            lst = list(FileList.get(ctrl))
            cur = ctrl.display.get("tasks", "roottask")
            ind = next((i for i, (_, j) in enumerate(lst) if j is cur), None)
            if ind is None:
                return
            new = min(len(lst)-1, max(0, ind+step))
            if new != ind:
                _oncurrentfile_cb(None, None, new)

        ctrl.display.updatedefaults(
            'keystroke',
            trackup   = lambda: _chg_cb2(1),
            trackdown = lambda: _chg_cb2(-1)
        )

class BeadToolbar(BokehView):  # pylint: disable=too-many-instance-attributes
    "Toolbar"
    _HELPERS  = BeadInput, RejectedBeadsInput, FileListInput
    __diagopen: TrackFileDialog
    __diagsave: SaveFileDialog

    def __init__(self, ctrl = None, **kwa):
        "Sets up the controller"
        super().__init__(ctrl = ctrl, **kwa)
        ctrl.theme.updatedefaults('keystroke',
                                  open    = "Control-o",
                                  save    = "Control-s",
                                  delbead = 'Shift-Delete',
                                  quit    = "Control-q")

        for cls in self._HELPERS:
            cls.init(ctrl)

        self.__messages = MessagesView(ctrl)
        self.__theme    = ctrl.theme.add(
            BeadToolbarTheme(width = kwa.get('width', BeadToolbarTheme.width)),
            False
        )
        ctrl.theme.add(FileDialogTheme(), False)

    def gettoolbarheight(self) -> float:
        "return the toolbar height"
        return self.__theme.height

    def observe(self, ctrl):
        "sets up observers"
        self.__messages.observe(ctrl)
        self.__diagopen = TrackFileDialog(self._ctrl)
        self.__diagsave = SaveFileDialog(self._ctrl)

    def addtodoc(self, ctrl, doc):
        "adds items to doc"
        super().addtodoc(ctrl, doc)
        tbar   = DpxToolbar(
            hasquit     = getattr(self._ctrl, 'FLEXXAPP', None) is not None,
            hasdoc      = True,
            helpmessage = self.__theme.placeholder,
            height      = self.__theme.height,
            width       = (
                ctrl.theme.get("theme", "appsize")[0]
                - ctrl.theme.get("theme", "borders")
            )
        )

        tbar.on_change("doc", lambda attr, old, new: ctrl.display.handle('changelog', args = {}))

        def _ontasks(old = None, **_):
            if 'bead'      in old:
                tbar.bead = ctrl.display.get("tasks", "bead")

            if 'taskcache' in old:
                root        = ctrl.display.get("tasks", "roottask")
                tbar.frozen = root is None
                if tbar.frozen:
                    return

                title = doc.title.split(':')[0]
                path  = (
                    root.path[0] if isinstance(root.path, (list, tuple)) else root.path
                )

                if path:
                    title += ':' + Path(path).stem
                doc.title = title

        def _onbtn_cb(attr, old, new):
            if attr == 'open':
                async def _run():
                    LOGS.debug("Running dialog open: %s", new)
                    await self.__diagopen.run(ctrl, doc)
                    LOGS.debug("Done running dialog open: %s", new)
                spawn(_run)
            elif attr == 'save':
                async def _run():
                    LOGS.debug("Running dialog save: %s", new)
                    await self.__diagsave.run(ctrl, doc)
                    LOGS.debug("Done running dialog save: %s", new)
                spawn(_run)
            elif attr == 'quit':
                ctrl.close()
            else:
                raise RuntimeError('Unknown toolbar button: '+attr)

        self.__messages.addtodoc(ctrl, doc, tbar)
        tbar.on_change('open', _onbtn_cb)
        tbar.on_change('save', _onbtn_cb)
        tbar.on_change('quit', _onbtn_cb)
        ctrl.display.updatedefaults('keystroke',
                                    open = partial(_onbtn_cb, 'open', 0, 0),
                                    save = partial(_onbtn_cb, 'save', 0, 0),
                                    quit = partial(_onbtn_cb, 'quit', 0, 0))
        ctrl.display.observe("tasks", _ontasks)

        self.__diagopen.setup(ctrl, doc)
        self.__diagsave.setup(ctrl, doc)

        for cls in self._HELPERS:
            cls.setup(ctrl, tbar, doc)

        mods  = self.defaultsizingmode(
            height = self.__theme.height,
            width  = ctrl.theme.get("theme", "appsize")[0]
        )
        return layouts.row([layouts.widgetbox(tbar, **mods)], **mods)

    def close(self):
        "Sets up the controller"
        super().close()
        del self.__diagopen
        del self.__diagsave
