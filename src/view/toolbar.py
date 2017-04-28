#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
from pathlib              import Path
from bokeh.layouts        import Row, widgetbox
from bokeh.models         import Div

from control.taskio       import TaskIO
from .dialog              import FileDialog
from .intinput            import BeadInput, RejectedBeadsInput
from .                    import BokehView

class TrackFileDialog(FileDialog):
    "A file dialog that doesn't open .gr files first"
    def __init__(self, ctrl):
        storage   = 'open'
        super().__init__(multiple  = 1,
                         storage   = storage,
                         config    = ctrl)

        def _defaultpath(ext):
            pot = self.storedpaths(ctrl, storage, ext)
            if ctrl.getGlobal('project').track.get(default = None) is None:
                pot = [i for i in pot if i.suffix != '.gr']
            return self.firstexistingpath(pot)
        self.config = _defaultpath, self.config[1]

class  ToolBar(BokehView):
    "Toolbar"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        self._open  = None
        self._save  = None
        self._quit  = None
        self._text  = None
        self._tools = []

        self._ctrl.getGlobal('project').message.default = ''
        msg = self._ctrl.getGlobal('config').message
        msg.defaults = { 'normal':  '<p>{}</p>',
                         'warning': '<p style="color:blue;">{}</p>',
                         'error':   '<p style="color:red>   {}</p>'
                       }
        css          = self._ctrl.getGlobal('css').title
        css.defaults = {'open': u'Open', 'save': u'Save', 'quit': u'Quit',
                        'open.dialog': u'Open a track or analysis file',
                        'save.dialog': u'Save an analysis file',
                        'working':     u'Please wait ...'}

        cnf = self._ctrl.getGlobal('config')
        cnf.catcherror.toolbar.default = True
        cnf.keypress.defaults          = {'open'     : "Control-o",
                                          'save'     : "Control-s",
                                          'quit'     : "Control-q"}

        self.__diagopen = TrackFileDialog(self._ctrl)
        self.__diagsave = FileDialog(config = self._ctrl, storage = 'save')

    def _getroots(self, _):
        "adds items to doc"
        css         = self._ctrl.getGlobal('css').title
        self._open  = self.button(self._onOpen,  css.open.get())
        self._save  = self.button(self._onSave,  css.save.get(), disabled = True)
        self._tools.extend([self._open, self._save])

        if self._ctrl.ISAPP:
            self._quit = self.button(self._ctrl.close, css.quit.get())
            self._tools.append(self._quit)
        self._text = Div(text = '                                     ')
        self._tools.append(self._text)

        self.__diagopen.filetypes = TaskIO.extensions(self._ctrl, 'openers')
        self.__diagopen.title     = css.open.dialog.get()
        self.__diagsave.filetypes = TaskIO.extensions(self._ctrl, 'savers')
        self.__diagsave.title     = css.save.dialog.get()

    def getroots(self, doc):
        "adds items to doc"
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

        msg     = self._ctrl.getGlobal('project').message
        working = self._ctrl.getGlobal('css').title.working.get()
        catch   = self._ctrl.getGlobal('config').catcherror.toolbar

        # pylint: disable=unused-variable
        @self._ctrl.observe
        def _onstartaction(recursive = None):
            if not recursive:
                msg.set((working, 'normal'))

        @self._ctrl.observe
        def _onstopaction(recursive = None, value = None, catcherror = None, **_):
            if not recursive:
                if value is None:
                    if working in self._text.text:
                        msg.set(('', 'normal'))
                    return

                if len(getattr(value, 'args', [])) == 2 and value.args[1] == 'treated':
                    msg.set((str(value.args[0]), 'warning'))
                else:
                    msg.set((str(value), 'error'))

                catcherror[0] = catch.get()

        templ = self._ctrl.getGlobal('config').message.getdict(..., fullnames = False)
        def _settext(text):
            self._text.text = templ[text.value[1]].format(text.value[0])

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

    @BokehView.action
    def _onOpen(self, *_):
        paths = self.__diagopen.open()
        if paths is not None:
            self._ctrl.openTrack(paths)

    @BokehView.action
    def _onSave(self,  *_):
        if self._save.disabled:
            return

        path = self.__diagsave.save()
        if path is not None:
            self._ctrl.saveTrack(path)

class  BeadToolBar(ToolBar):
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
