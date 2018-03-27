#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
import time
from typing               import Callable, TYPE_CHECKING, Iterator, Tuple, Any
from pathlib              import Path

import bokeh.core.properties   as props

from bokeh                import layouts
from bokeh.models         import Widget
from bokeh.io             import curdoc

from utils.gui            import parseints
from utils.logconfig      import getLogger
from control.taskio       import TaskIO
from control.beadscontrol import DataSelectionBeadController
from .dialog              import FileDialog
from .base                import BokehView, threadmethod, spawn
from .static              import ROUTE
LOGS  = getLogger(__name__)

if TYPE_CHECKING:
    from model.task import RootTask # pylint: disable=unused-import

STORAGE = 'open', 'save'
class TrackFileDialog(FileDialog):
    "A file dialog that doesn't open .gr files first"
    def __init__(self, ctrl):
        super().__init__(multiple  = 1,
                         storage   = STORAGE[0],
                         config    = ctrl)

        def _defaultpath(ext, bopen):
            assert bopen

            pot = self.storedpaths(ctrl, STORAGE[0], ext)
            if ctrl.globals.project.track.get(default = None) is None:
                pot = [i for i in pot if i.suffix != '.gr']
            return self.firstexistingpath(pot)

        self.__store: Callable = self.config[1]
        self.config            = _defaultpath, None

    def setup(self, ctrl, _):
        "sets the document"
        self.filetypes = '*|'+TaskIO.extensions(ctrl, 'openers')
        self.title     = ctrl.globals.css.title.open.dialog.get()

    async def run(self, ctrl, doc):
        "runs the dialog"
        paths = await threadmethod(self.open)
        if paths is not None:
            def _fcn():
                with ctrl.action:
                    self.__store(paths, True) # pylint: disable=not-callable
                    ctrl.tasks.opentrack(paths)
            doc.add_next_tick_callback(_fcn)

class SaveFileDialog(FileDialog):
    "A file dialog that adds a default save path"
    def __init__(self, ctrl):
        super().__init__(storage = STORAGE[1],
                         config  = ctrl)
        def _defaultpath(ext, bopen):
            assert not bopen
            pot = [i for i in self.storedpaths(ctrl, STORAGE[0], ext) if i.exists()]
            ope = next((i for i in pot if not i.suffix in ('', '.gr')), None)
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

        self.__store = self.config[1]
        self.config  = _defaultpath, None

    def setup(self, ctrl, _):
        "sets the document"
        self.filetypes = TaskIO.extensions(ctrl, 'savers')
        self.title     = ctrl.globals.css.title.save.dialog.get()

    async def run(self, ctrl, doc):
        "runs the dialog"
        paths = await threadmethod(self.save)
        if paths is not None:
            def _fcn():
                with ctrl.action:
                    self.__store(paths, False) # pylint: disable=not-callable
                    ctrl.tasks.savetrack(paths)
            doc.add_next_tick_callback(_fcn)

class DpxToolbar(Widget):
    "Toolbar model"
    __css__            = ROUTE+"/view.css"
    __javascript__     = ROUTE+"/jquery.min.js"
    __implementation__ = 'toolbar.coffee'
    open        = props.Int(0)
    save        = props.Int(0)
    quit        = props.Int(0)
    bead        = props.Int(-1)
    discarded   = props.String('')
    accepted    = props.String('')
    currentbead = props.Bool(True)
    currentfile = props.Int(-1)
    filelist    = props.List(props.String)
    seltype     = props.Bool(True)
    message     = props.String('')
    frozen      = props.Bool(True)
    hasquit     = props.Bool(False)
    def __init__(self, **kwa):
        super().__init__(name = 'Main:toolbar', **kwa)

class MessagesInput:
    "Everything related to messages"
    @staticmethod
    def init(ctrl):
        "initializes globals"
        ctrl.globals.project.message.default = None
        msg = ctrl.globals.css.message
        siz = 'heigth: 28px; margin-top: 0px;'
        msg.defaults = dict(normal  = '<p style="%s">{}</p>' % siz,
                            warning = '<p style="%s color:blue;">{}</p>' % siz,
                            error   = '<p style="%s color:red;"> {}</p>' % siz,
                            busy    = u'Please wait ...',
                            period  = 50,
                            width   = 350)
        msg.timeout.defaults = dict(normal  = 1000,
                                    error   = 50000,
                                    warning = 50000)

    @staticmethod
    def setup(ctrl, tbar: DpxToolbar, doc):
        "sets-up the gui"
        msg   = ctrl.globals.project.message
        busy  = ctrl.globals.css.message.busy.get(), 'normal'

        @ctrl.display.observe
        def _onstartaction(recursive = None):      # pylint: disable=unused-variable
            if not recursive:
                _settext(busy)

        @ctrl.display.observe
        def _onstartcomputation(recursive = None): # pylint: disable=unused-variable
            if recursive:
                return
            val = msg.get()
            if val is None or (isinstance(val, tuple) and val[1] == 'normal'):
                _settext(busy)

        def _observer(recursive = None, value = None, catcherror = None, **_):
            if not recursive and value is not None:
                LOGS.info('stop')
                msg.set(value)
                catcherror[0] = getattr(ctrl, 'CATCHERROR', True)
        ctrl.display.observe("stopaction", "stopcomputation", _observer)

        templ      = ctrl.globals.css.message.getdict(..., fullnames = False)
        timeout    = ctrl.globals.css.message.timeout.getdict(..., fullnames = False)
        timeout    = {i: j*1e-3 for i, j in timeout.items()}

        last: list = [None, None, timeout['normal']]
        def _setmsg():
            if last[0] is None:
                return

            if last[0] != '':
                tbar.message = last[0]
                last[0] = ''
                last[1] = time.time()+last[2]

            elif last[1] < time.time():
                last[0]         = None
                tbar.message = ''
        doc.add_periodic_callback(_setmsg, ctrl.globals.css.message.period.get())

        def _settext(text):
            text = getattr(text, 'value', text)
            if text is None:
                return
            elif isinstance(text, Exception):
                args = getattr(text, 'args', tuple())
                if len(args) == 1:
                    args = args[0], 'error'
                elif len(args) != 2:
                    args = text,    'error'
                elif args[1] not in templ:
                    args = str(args), 'error'
            else:
                args = text

            val = templ[str(args[1])].format(str(args[0])
                                             .replace('<', '&lt')
                                             .replace('>', '&gt'))
            if args[1] == 'error':
                LOGS.error(str(args[0]))
            elif args[1] == 'warning':
                LOGS.warning(str(args[0]))

            last[0] = val
            last[1] = time.time()+timeout.get(args[1], timeout['normal'])
            last[2] = timeout.get(args[1], timeout['normal'])
            if curdoc() is doc:
                try:
                    tbar.message = val
                    return
                except RuntimeError:
                    pass

        ctrl.globals.project.message.observe(_settext)

class BeadInput:
    "Spinner for controlling the current bead"
    @staticmethod
    def init(ctrl):
        "Sets up the controller"
        ctrl.theme.updatedefaults('keystroke', beadup = 'PageUp', beaddown = 'PageDown')

    @staticmethod
    def setup(ctrl, tbar: DpxToolbar, _):
        "adds items to doc"
        bdctrl = DataSelectionBeadController(ctrl)

        def _chg_cb(attr, old, new):
            with ctrl.action:
                bdctrl.bead = new
            tbar.bead = bdctrl.bead

        def _onproject(_ = None):
            bead  = bdctrl.bead
            avail = set(bdctrl.availablebeads)
            if bead not in avail:
                if any(i > bead for i in avail):
                    bdctrl.bead = bead+1
                elif any(i < bead for i in avail):
                    bdctrl.bead = bead-1
                else:
                    tbar.bead = bead
            else:
                tbar.bead = bead

        tbar.on_change('bead', _chg_cb)
        ctrl.globals.project.observe('track', 'bead', _onproject)
        ctrl.observe("updatetask", "addtask", "removetask", lambda **_: _onproject())
        ctrl.display.updatedefaults('keystroke',
                                    beadup   = lambda: _chg_cb('', '', bdctrl.bead+1),
                                    beaddown = lambda: _chg_cb('', '', bdctrl.bead-1))

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
                bdctrl.discarded = set(bdctrl.discarded) | {bead}

        def _ondiscard_currentbead_cb(attr, old, value):
            _ondiscard_currentbead()

        def _onaccepted_cb(attr, old, new):
            beads = set(bdctrl.allbeads) - parseints(new)
            if (not tbar.seltype) and beads != set(bdctrl.discarded):
                with ctrl.action:
                    bdctrl.discarded = beads

        def _ondiscarded_cb(attr, old, new):
            beads = parseints(new)
            if tbar.seltype and beads != set(bdctrl.discarded):
                with ctrl.action:
                    bdctrl.discarded = beads

        def _onproject():
            disc = set(bdctrl.discarded)
            acc  = set(bdctrl.allbeads) - disc
            tbar.update(accepted  = ', '.join(str(i) for i in sorted(acc)),
                        discarded = ', '.join(str(i) for i in sorted(disc)))

        tbar.on_change('currentbead',            _ondiscard_currentbead_cb)
        tbar.on_change('discarded',              _ondiscarded_cb)
        tbar.on_change('accepted',               _onaccepted_cb)
        ctrl.display.updatedefaults('keystroke', delbead = _ondiscard_currentbead)
        ctrl.observe("updatetask", "addtask", "removetask", lambda **_: _onproject())
        ctrl.globals.project.track.observe(_onproject)

class FileList:
    "Selection of opened files"
    def __init__(self, ctrl):
        self._ctrl: Any = ctrl
        fnames = ctrl.globals.css.filenames
        fnames.defaults = {'many': '{Path(files[0]).stem} + ...',
                           'single': '{Path(path).stem}'}

    @staticmethod
    def __pathname(ctrl, task):
        if task.key:
            return task.key

        lst = task.path
        cnf = ctrl.globals.css.filenames
        if isinstance(lst, (tuple, list)):
            if len(lst) > 1:
                # pylint: disable=eval-used
                return eval(f'f"{cnf.many.get()}"', dict(files = lst, Path = Path))
            lst = lst[0]
        # pylint: disable=eval-used
        return eval(f'f"{cnf.single.get()}"', dict(path = lst, Path = Path))

    @classmethod
    def get(cls, ctrl) -> Iterator[Tuple[str, 'RootTask']]:
        "returns current roots"
        lst  = [next(i) for i in getattr(ctrl, 'tasks', ctrl).tasklist(...)]
        return ((cls.__pathname(ctrl, i), i) for i in lst)

    def __call__(self) -> Iterator[Tuple[str, 'RootTask']]:
        "returns current roots"
        return self.get(self._ctrl)

class FileListInput:
    "Selection of opened files"
    @staticmethod
    def init(ctrl):
        "Sets up the controller"
        FileList(ctrl = ctrl)

    @staticmethod
    def setup(ctrl, tbar: DpxToolbar, _):
        "sets-up the gui"
        @ctrl.observe("opentrack", "closetrack")
        def _setfilelist(model = None, **_):
            vals  = list(FileList.get(ctrl))
            mdls  = [i for _, i in vals]
            if model[0] in mdls:
                index = mdls.index(model[0])
            else:
                cur   = ctrl.globals.project.track.get()
                index = mdls.index(cur) if cur in mdls else 0

            tbar.update(currentfile = index, filelist = [i for i, _ in vals])

        def _oncurrentfile_cb(attr, old, new):
            new = int(new)
            if new == -1:
                return

            track = ctrl.globals.project.track
            lst   = list(FileList.get(ctrl))
            if new >= len(lst):
                _setfilelist(model = [track.get()])
            else:
                track.set(lst[new][1])

        tbar.on_change('currentfile', _oncurrentfile_cb)

class BeadToolbar(BokehView): # pylint: disable=too-many-instance-attributes
    "Toolbar"
    _HELPERS = BeadInput, RejectedBeadsInput, MessagesInput, FileListInput

    def __init__(self, ctrl = None, **kwa):
        "Sets up the controller"
        super().__init__(ctrl = ctrl, **kwa)
        css          = ctrl.globals.css.title
        css.defaults = {'open': u'Open', 'save': u'Save', 'quit': u'Quit',
                        'open.dialog': u'Open a track or analysis file',
                        'save.dialog': u'Save an analysis file'}
        ctrl.theme.updatedefaults('keystroke',
                                  open    = "Control-o",
                                  save    = "Control-s",
                                  delbead = 'Shift-Delete',
                                  quit    = "Control-q")

        for cls in self._HELPERS:
            cls.init(ctrl)

        self.__diagopen = TrackFileDialog(self._ctrl)
        self.__diagsave = SaveFileDialog(self._ctrl)

    def getroots(self, ctrl, doc):
        "adds items to doc"
        assert doc is not None
        self._doc = doc
        tbar   = DpxToolbar(hasquit = getattr(self._ctrl, 'FLEXXAPP', None) is not None)

        def _onbtn_cb(attr, old, new):
            if attr == 'open':
                async def _run():
                    await self.__diagopen.run(ctrl, doc)
                spawn(_run)
            elif attr == 'save':
                async def _run():
                    await self.__diagsave.run(ctrl, doc)
                spawn(_run)
            elif attr == 'quit':
                ctrl.close()
            else:
                raise RuntimeError('Unknown toolbar button: '+attr)

        tbar.on_change('open', _onbtn_cb)
        tbar.on_change('save', _onbtn_cb)
        tbar.on_change('quit', _onbtn_cb)

        self.__diagopen.setup(ctrl, doc)
        self.__diagsave.setup(ctrl, doc)
        self.__setup_title(ctrl, doc)
        for cls in self._HELPERS:
            cls.setup(ctrl, tbar, doc)

        ctrl.display.updatedefaults('keystroke',
                                    open = lambda: _onbtn_cb('open', 0, 0),
                                    save = lambda: _onbtn_cb('save', 0, 0),
                                    quit = lambda: _onbtn_cb('save', 0, 0))

        def _onproject(items):
            if 'track' in items:
                tbar.frozen = items['track'].value is items.empty
        ctrl.globals.project.observe(_onproject)
        mods = self.defaultsizingmode(height = 50)
        return layouts.row([layouts.widgetbox(tbar, **mods)], **mods)

    def close(self):
        "Sets up the controller"
        super().close()
        del self.__diagopen
        del self.__diagsave

    @staticmethod
    def __setup_title(ctrl, doc):
        def _title(item):
            path = getattr(item.value, 'path', None)
            if isinstance(path, (list, tuple)):
                path = path[0]
            title = doc.title.split(':')[0]
            if path:
                title += ':' + Path(path).stem
            doc.title = title

        ctrl.globals.project.track.observe(_title)
