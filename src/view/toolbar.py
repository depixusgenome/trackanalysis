#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
from typing               import Callable, TYPE_CHECKING
from pathlib              import Path

import bokeh.core.properties   as props

from bokeh                import layouts
from bokeh.models         import Widget
from bokeh.io             import curdoc

from control.taskio       import TaskIO
from control.beadscontrol import BeadController
from utils.gui            import parseints
from .dialog              import FileDialog
from .base                import BokehView, threadmethod, spawn, Action
from .static              import ROUTE

STORAGE = 'open', 'save'
class TrackFileDialog(FileDialog):
    "A file dialog that doesn't open .gr files first"
    def __init__(self, ctrl):
        super().__init__(multiple  = 1,
                         storage   = STORAGE[0],
                         config    = ctrl)

        self.__store: Callable = self.config[1]
        self.__ctrl            = ctrl
        self.__doc             = None

        def _defaultpath(ext, bopen):
            assert bopen

            pot = self.storedpaths(ctrl, STORAGE[0], ext)
            if ctrl.getGlobal('project').track.get(default = None) is None:
                pot = [i for i in pot if i.suffix != '.gr']
            return self.firstexistingpath(pot)
        self.config    = _defaultpath, None

    def setup(self, doc):
        "sets the document"
        self.__doc = doc
        assert doc is not None
        self.filetypes = '*|'+TaskIO.extensions(self.__ctrl, 'openers')
        self.title     = self.__ctrl.getGlobal('css').title.open.dialog.get()

    async def run(self):
        "runs the dialog"
        paths = await threadmethod(self.open)
        if paths is not None:
            def _fcn():
                with Action(self.__ctrl):
                    self.__store(paths, True) # pylint: disable=not-callable
                    self.__ctrl.openTrack(paths)
            self.__doc.add_next_tick_callback(_fcn)

class SaveFileDialog(FileDialog):
    "A file dialog that adds a default save path"
    def __init__(self, ctrl):
        super().__init__(storage = STORAGE[1],
                         config  = ctrl)

        self.__store = self.config[1]
        self.__ctrl  = ctrl
        self.__doc   = None

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

        self.config  = _defaultpath, None

    def setup(self, doc):
        "sets the document"
        self.__doc = doc
        self.filetypes = TaskIO.extensions(self.__ctrl, 'savers')
        self.title     = self.__ctrl.getGlobal('css').title.save.dialog.get()

    async def run(self):
        "runs the dialog"
        paths = await threadmethod(self.save)
        if paths is not None:
            def _fcn():
                with Action(self.__ctrl):
                    self.__store(paths, False) # pylint: disable=not-callable
                    self.__ctrl.saveTrack(paths)
            self.__doc.add_next_tick_callback(_fcn)

class DpxToolbar(Widget):
    "Toolbar model"
    __css__            = ROUTE+"/view.css"
    __implementation__ = 'toolbar.coffee'
    open      = props.Int(0)
    save      = props.Int(0)
    quit      = props.Int(0)
    bead      = props.Int(-1)
    discarded = props.String('')
    message   = props.String('')
    frozen    = props.Bool(True)
    hasquit   = props.Bool(False)
    def __init__(self, **kwa):
        super().__init__(name = 'Main:toolbar', **kwa)

class MessagesInput(BokehView):
    "Everything related to messages"
    def __init__(self, *args, **kwargs):
        "initializes globals"
        super().__init__(*args, **kwargs)
        self._ctrl.getGlobal('project').message.default = None
        msg = self._ctrl.getGlobal('css').message
        siz = 'heigth: 28px; margin-top: 0px;'
        msg.defaults = dict(normal  = '<p style="%s">{}</p>' % siz,
                            warning = '<p style="%s color:blue;">{}</p>' % siz,
                            error   = '<p style="%s color:red;"> {}</p>' % siz,
                            busy    = u'Please wait ...',
                            width   = 350)

    def setup(self, toolbar, doc):
        "sets-up the gui"
        ctrl  = self._ctrl

        msg   = ctrl.getGlobal('project').message
        busy  = ctrl.getGlobal('css').message.busy.get(), 'normal'
        catch = ctrl.getGlobal('config').catcherror.toolbar

        @ctrl.observe
        def _onstartaction(recursive = None):      # pylint: disable=unused-variable
            if not recursive:
                msg.set(busy)

        @ctrl.observe
        def _onstartcomputation(recursive = None): # pylint: disable=unused-variable
            if recursive:
                return
            val = msg.get()
            if val is None or (isinstance(val, tuple) and val[1] == 'normal'):
                msg.set(busy)

        def _observer(recursive = None, value = None, catcherror = None, **_):
            if not recursive:
                if value is None:
                    if busy == msg.get():
                        msg.set(None)
                else:
                    msg.set(value)
                    catcherror[0] = catch.get()
        ctrl.observe("stopaction", "stopcomputation", _observer)

        templ = ctrl.getGlobal('css').message.getdict(..., fullnames = False)
        def _settext(text):
            if text.value is None:
                val = ''
            elif isinstance(text.value, Exception):
                args = getattr(text.value, 'args', tuple())
                if len(args) == 1:
                    args = text.value.args[0], 'error'
                elif len(args) != 2:
                    args = text.value,         'error'
                val = templ[args[1]].format(str(args[0]))
            else:
                val = templ[text.value[1]].format(text.value[0])
            if curdoc() is doc:
                try:
                    toolbar.message = val
                    return
                except RuntimeError:
                    pass

            fcn = lambda: setattr(toolbar, 'message', val)
            doc.add_next_tick_callback(fcn)

        ctrl.getGlobal('project').message.observe(_settext)

class BeadView(BokehView):
    "Widget for controlling the current beads"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._bdctrl = BeadController(self._ctrl)

    if TYPE_CHECKING:
        def getroots(self, doc):
            assert False

class BeadInput(BeadView):
    "Spinner for controlling the current bead"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        cnf = self._ctrl.getGlobal('config')
        cnf.keypress.defaults = {'beadup'   : 'PageUp',
                                 'beaddown' : 'PageDown'}
        self.__toolbar = None

    def setup(self, toolbar):
        "adds items to doc"
        self.__toolbar  = toolbar

        def _onchange_cb(attr, old, new):
            with self.action:
                self._bdctrl.bead = new

        def _onproject(_):
            self._bdctrl.bead = self._bdctrl.bead

        def _onupdatetask(**_):
            self._bdctrl.bead = self._bdctrl.bead

        toolbar.on_change('bead', _onchange_cb)
        self._ctrl.getGlobal('project').observe('track', 'bead', _onproject)
        self._ctrl.observe("updatetask", "addtask", "removetask", _onupdatetask)

        self._keys.addKeyPress(('keypress.beadup',
                                lambda: _onchange_cb('', '', toolbar.bead+1)))
        self._keys.addKeyPress(('keypress.beaddown',
                                lambda: _onchange_cb('', '', toolbar.bead-1)))

class RejectedBeadsInput(BeadView):
    "Text dealing with rejected beads"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__toolbar = None
        self._ctrl.getGlobal('config').keypress.defaults = {'delbead': 'Shift-Delete'}

    def setup(self, toolbar):
        "sets-up the gui"
        def _ondiscard_current(*_):
            if self._bdctrl.bead is not None:
                with self.action:
                    self._bdctrl.discarded = self._bdctrl.discarded | {self._bdctrl.bead}

        def _ondiscarded_cb(attr, old, new):
            with self.action:
                self._bdctrl.discarded = parseints(new)

        def _onupdatetask(**_):
            self.__toolbar.discarded = ','.join(self._bdctrl.discarded)

        def _onremovetask(**_):
            self.__toolbar.discarded = ','.join(self._bdctrl.discarded)

        def _onproject():
            self.__toolbar.discarded = ', '.join(str(i) for i in sorted(self._bdctrl.discarded))

        self._keys.addKeyPress(('keypress.delbead', _ondiscard_current))
        toolbar.on_change('discarded',              _ondiscarded_cb)
        self._ctrl.observe("updatetask", "addtask", _onupdatetask)
        self._ctrl.observe("removetask",            _onremovetask)
        self._ctrl.getGlobal('project').track.observe(_onproject)
        self.__toolbar = toolbar

class BeadToolbar(BokehView): # pylint: disable=too-many-instance-attributes
    "Toolbar"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        css          = self._ctrl.getGlobal('css').title
        css.defaults = {'open': u'Open', 'save': u'Save', 'quit': u'Quit',
                        'open.dialog': u'Open a track or analysis file',
                        'save.dialog': u'Save an analysis file'}

        cnf = self._ctrl.getGlobal('config')
        cnf.catcherror.toolbar.default = True
        cnf.keypress.defaults = {'open':    "Control-o",
                                 'save':    "Control-s",
                                 'delbead': 'Shift-Delete',
                                 'quit':    "Control-q"}

        self.__bead     = BeadInput(**kwa)
        self.__rejected = RejectedBeadsInput(**kwa)
        self.__messages = MessagesInput(**kwa)
        self.__toolbar  = None
        self.__diagopen = TrackFileDialog(self._ctrl)
        self.__diagsave = SaveFileDialog(self._ctrl)

    def getroots(self, doc):
        "adds items to doc"
        assert doc is not None
        self._doc = doc

        self.__toolbar  = DpxToolbar(hasquit = self._ctrl.ISAPP)

        def _onbtn_cb(attr, old, new):
            if attr == 'open':
                spawn(self.__diagopen.run)
            elif attr == 'save':
                spawn(self.__diagsave.run)
            elif attr == 'quit':
                self._ctrl.close()
            else:
                raise RuntimeError('Unknown toolbar button: '+attr)

        self.__toolbar.on_change('open', _onbtn_cb)
        self.__toolbar.on_change('save', _onbtn_cb)
        self.__toolbar.on_change('quit', _onbtn_cb)
        self._keys.addKeyPress(('keypress.open',  lambda: _onbtn_cb('open', 0, 0)),
                               ('keypress.save',  lambda: _onbtn_cb('save', 0, 0)),
                               ('keypress.quit',  lambda: _onbtn_cb('save', 0, 0)))

        self.__diagopen.setup(doc)
        self.__diagsave.setup(doc)
        self.__messages.setup(self.__toolbar, doc)
        self.__bead    .setup(self.__toolbar)
        self.__rejected.setup(self.__toolbar)
        self.__setup_title(doc)

        def _onproject(items):
            if 'track' in items:
                self.__toolbar.frozen = items['track'].value is items.empty
        self._ctrl.getGlobal("project").observe(_onproject)
        mods = self.defaultsizingmode(height = 30)
        return layouts.row([layouts.widgetbox(self.__toolbar, **mods)], **mods)

    def close(self):
        "Sets up the controller"
        super().close()
        del self.__bead
        del self.__rejected
        del self.__messages
        del self.__toolbar
        del self.__diagopen
        del self.__diagsave

    def __setup_title(self, doc):
        def _title(item):
            path = getattr(item.value, 'path', None)
            if isinstance(path, (list, tuple)):
                path = path[0]
            title = doc.title.split(':')[0]
            if path is not None and len(path) > 0:
                title += ':' + Path(path).stem
            doc.title = title

        self._ctrl.getGlobal("project").track.observe(_title)
