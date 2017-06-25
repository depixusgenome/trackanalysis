#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
from typing               import Callable, TYPE_CHECKING # pylint: disable=unused-import
from pathlib              import Path
import re

import numpy                   as np
import bokeh.core.properties   as props

from bokeh.models         import LayoutDOM
from bokeh.io             import curdoc

from control.taskio       import TaskIO
from model.task           import DataSelectionTask
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

        self.__store = self.config[1] # type: Callable
        self.__ctrl  = ctrl
        self.__doc   = None

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

class DpxToolbar(LayoutDOM):
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
                toolbar.message = val
            else:
                fcn = lambda: setattr(toolbar, 'message', val)
                doc.add_next_tick_callback(fcn)

        ctrl.getGlobal('project').message.observe(_settext)

class BeadView(BokehView):
    "Widget for controlling the current beads"
    @property
    def _root(self):
        return self._ctrl.getGlobal("project").track.get()

    @property
    def _bead(self):
        return self._ctrl.getGlobal("project").bead.get()

    @_bead.setter
    def _bead(self, val):
        return self._ctrl.getGlobal("project").bead.set(val)

    def _isdiscardedbeads(self, parent, task):
        return isinstance(task, DataSelectionTask) and parent is self._root

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

        self.__beads   = np.empty((0,), dtype = 'i4')
        self.__toolbar = None

    def setup(self, toolbar):
        "adds items to doc"
        self.__toolbar  = toolbar
        toolbar.on_change('bead', self.__onchange_cb)
        self._ctrl.getGlobal('project').observe('track', 'bead', self.__onproject)
        self._ctrl.observe("updatetask", "addtask", "removetask", self.__onupdatetask)

        self._keys.addKeyPress(('keypress.beadup',
                                lambda: self.__onchange_cb('', '', toolbar.bead+1)))
        self._keys.addKeyPress(('keypress.beaddown',
                                lambda: self.__onchange_cb('', '', toolbar.bead-1)))

    def __setbeads(self):
        "returns the active beads"
        root  = self._root
        track = self._ctrl.track(root)
        if track is None:
            return []

        task  = self._ctrl.task(root, DataSelectionTask)
        beads = set(track.beadsonly.keys()) - set(getattr(task, 'discarded', []))
        self.__beads = np.sort(tuple(beads)) if len(beads) else np.empty((0,), dtype = 'i4')
        if self.__toolbar.bead not in self.__beads:
            self.__setvalue(self.__beads[0])

    def __setvalue(self, bead):
        if len(self.__beads) == 0:
            return

        if bead is None:
            bead = self.__beads[0]
        elif bead not in self.__beads:
            bead = self.__beads[min(len(self.__beads)-1,
                                    np.searchsorted(self.__beads, bead))]

        if bead == self._bead:
            self.__toolbar.bead = bead
        else:
            with self.action:
                self._bead = bead

    def __onchange_cb(self, attr, old, new):
        self.__setvalue(new)

    def __onproject(self, items):
        if 'track' in items:
            self.__setbeads()
        self.__setvalue(self._bead)

    def __onupdatetask(self, parent = None, task = None, **_):
        if self._isdiscardedbeads(parent, task):
            self.__setbeads()
            self.__setvalue(self._bead)

class RejectedBeadsInput(BeadView):
    "Text dealing with rejected beads"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__toolbar = None
        self._ctrl.getGlobal('config').keypress.defaults = {'delbead': 'Shift-Delete'}

    def setup(self, toolbar):
        "sets-up the gui"
        self._keys.addKeyPress(('keypress.delbead', self.__ondiscard_current))
        toolbar.on_change('discarded',              self.__ondiscarded_cb)
        self._ctrl.observe("updatetask", "addtask", self.__onupdatetask)
        self._ctrl.observe("removetask",            self.__onremovetask)
        self._ctrl.getGlobal('project').track.observe(self.__onproject)
        self.__toolbar = toolbar

    def __current(self):
        task = self._ctrl.task(self._root, DataSelectionTask)
        return set(getattr(task, 'discarded', []))

    def __ondiscard_current(self, *_):
        beads = self.__current()
        beads.add(self._bead)
        self.__ondiscard(beads)

    def __ondiscarded_cb(self, attr, old, new):
        vals = set()
        for i in re.split('[:;,]', new):
            try:
                vals.add(int(i))
            except ValueError:
                continue
        self.__ondiscard(vals)

    def __ondiscard(self, vals:set):
        if vals == self.__current():
            return

        root = self._root
        task = self._ctrl.task(root, DataSelectionTask)
        with self.action:
            if task is None:
                self._ctrl.addTask(root, DataSelectionTask(discarded = list(vals)), index = 1)
            elif len(vals) == 0:
                self._ctrl.removeTask(root, task)
            else:
                self._ctrl.updateTask(root, task, discarded = list(vals))

    def __onupdatetask(self, parent = None, task = None, **_):
        if self._isdiscardedbeads(parent, task):
            self.__toolbar.discarded = ','.join(str(i) for i in sorted(task.discarded))

    def __onremovetask(self, parent = None, task = None, **_):
        if self._isdiscardedbeads(parent, task):
            self.__toolbar.discarded = ''

    def __onproject(self):
        task  = self._ctrl.task(self._root, DataSelectionTask)
        beads = getattr(task, 'discarded', ())
        self.__toolbar.discarded = ', '.join(str(i) for i in sorted(beads))

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
        return self.__toolbar,

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
