#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
from typing               import Callable # pylint: disable=unused-import
from pathlib              import Path
from bokeh.layouts        import Row, widgetbox
from bokeh.models         import Div
from bokeh.io             import curdoc

from control.taskio       import TaskIO
from .dialog              import FileDialog
from .intinput            import BeadInput, RejectedBeadsInput
from .base                import BokehView, threadmethod, spawn, Action

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

class ToolBar(BokehView): # pylint: disable=too-many-instance-attributes
    "Toolbar"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        self._open  = None
        self._save  = None
        self._quit  = None
        self._text  = None
        self._tools = []

        self._ctrl.getGlobal('project').message.default = None
        msg = self._ctrl.getGlobal('css').message
        msg.defaults = dict(normal  = '<p>{}</p>',
                            warning = '<p style="color:blue;">{}</p>',
                            error   = '<p style="color:red;"> {}</p>',
                            busy    = u'Please wait ...',
                            width   = 350)
        css          = self._ctrl.getGlobal('css').title
        css.defaults = {'open': u'Open', 'save': u'Save', 'quit': u'Quit',
                        'open.dialog': u'Open a track or analysis file',
                        'save.dialog': u'Save an analysis file'}

        cnf = self._ctrl.getGlobal('config')
        cnf.catcherror.toolbar.default = True
        cnf.keypress.defaults          = {'open'     : "Control-o",
                                          'save'     : "Control-s",
                                          'quit'     : "Control-q"}

        self.__diagopen = TrackFileDialog(self._ctrl)
        self.__diagsave = SaveFileDialog(self._ctrl)

    def _getroots(self, doc):
        "adds items to doc"
        css         = self._ctrl.getGlobal('css').title
        self._open  = self.button(self._onOpen,  css.open.get())
        self._save  = self.button(self._onSave,  css.save.get(), disabled = True)
        self._tools.extend([self._open, self._save])

        if self._ctrl.ISAPP:
            self._quit = self.button(self._ctrl.close, css.quit.get())
            self._tools.append(self._quit)
        self._text = Div(text = ' ',
                         width = self._ctrl.getGlobal('css').message.width.get())
        self._tools.append(self._text)

        self.__diagopen.setup(doc)
        self.__diagsave.setup(doc)

    def getroots(self, doc):
        "adds items to doc"
        self._doc = doc
        self._getroots(doc)

        def _title(item):
            path = getattr(item.value, 'path', None)
            if isinstance(path, (list, tuple)):
                path = path[0]
            title = doc.title.split(':')[0]
            if path is not None and len(path) > 0:
                title += ':' + Path(path).stem
            doc.title = title

        self._ctrl.getGlobal("project").track.observe(_title)

        msg   = self._ctrl.getGlobal('project').message
        busy  = self._ctrl.getGlobal('css').message.busy.get()
        catch = self._ctrl.getGlobal('config').catcherror.toolbar

        @self._ctrl.observe
        def _onstartaction(recursive = None):      # pylint: disable=unused-variable
            if not recursive:
                msg.set((busy, 'normal'))

        @self._ctrl.observe
        def _onstartcomputation(recursive = None): # pylint: disable=unused-variable
            if recursive:
                return
            val = msg.get()
            if val is None or (isinstance(val, tuple) and val[1] == 'normal'):
                msg.set((busy, 'normal'))

        def _observer(recursive = None, value = None, catcherror = None, **_):
            if not recursive:
                if value is None:
                    val = msg.get()
                    if val is not None and busy == val[0]:
                        msg.set(None)
                else:
                    msg.set(value)
                    catcherror[0] = catch.get()
        self._ctrl.observe("stopaction", "stopcomputation", _observer)

        templ = self._ctrl.getGlobal('css').message.getdict(..., fullnames = False)
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
            if curdoc() is self._doc:
                self._text.text = val
            else:
                self._doc.add_next_tick_callback(lambda: setattr(self._text, 'text', val))

        self._ctrl.getGlobal('project').message.observe(_settext)
        self.enableOnTrack(self._save)

        return Row(children = self._tools, sizing_mode = 'fixed'),

    def close(self):
        "Sets up the controller"
        super().close()
        del self._tools
        del self._open
        del self._save
        del self._quit
        del self.__diagopen
        del self.__diagsave

    def _onOpen(self, *_):
        spawn(self.__diagopen.run)

    def _onSave(self,  *_):
        spawn(self.__diagsave.run)

class BeadToolBar(ToolBar):
    "Toolbar with a bead spinner"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._beads     = BeadInput(**kwa)
        self._discarded = RejectedBeadsInput(**kwa)
        self._ctrl.getGlobal('css').beadtoobar.boxwidth.default = 200

    @property
    def __beadchildren(self):
        return self._beads, self._discarded

    def _getroots(self, doc):
        super()._getroots(doc)
        width    = self._ctrl.getGlobal("css").beadtoobar.boxwidth.get()
        children = self.__beadchildren
        for attr in children:
            attr.getroots(doc)

        self._tools.insert(2, widgetbox(self._beads.input, width = 2*self._beads.input.width))
        self._tools.insert(3, widgetbox(self._discarded.input, width = width))
        self.enableOnTrack(*(i.input for i in children))

    def close(self):
        "Sets up the controller"
        super().close()
        for attr in self.__beadchildren:
            attr.close()
