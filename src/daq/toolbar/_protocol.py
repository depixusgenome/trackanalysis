#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Set the protocol
"""
from abc                import abstractmethod
from contextlib         import contextmanager
from copy               import deepcopy
from functools          import partial
from typing             import Tuple, TypeVar, Generic, Union, ClassVar, cast

from utils              import initdefaults
from utils.inspection   import templateattribute
from utils.logconfig    import getLogger
from modaldialog        import dialog

from ..model            import (DAQConfig, DAQProtocol, DAQManual, DAQRamp, DAQProbe,
                                ConfigObject)

LOGS   = getLogger(__name__)

class DAQProtocolTheme(ConfigObject):
    "Basic theme for a modal dialog"
    name     = ""
    title    = ""
    width    = 90
    body     = [["Cycles", "%(cyclecount)d"],
                ["Frame rate", "%(framerate)d"],
                ["Phases", "Zmag / speed / duration"],
                ["{index}",
                 "%(phases[{index}].zmag).3of",
                 "%(phases[{index}].speed).3of",
                 "%(phases[{index}].duration)of",
                ]]
    firstwidth = 250
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class DAQAttrRange(ConfigObject):
    "attribute value and range"
    vmin   = 0.
    value  = .5
    vmax   = 1.
    inc    = .1
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def move(self, moveup) -> float:
        """
        incremented or decremented value
        """
        return min(self.vmax, max(self.vmin, self.value + (1 if moveup else -1)*self.inc))

class DAQManualConfig(ConfigObject):
    """
    DAQ manual values
    """
    name      = "daqmanual"
    framerate = 30
    roi       = list(DAQConfig.defaultbead.roi)
    zmag      = DAQAttrRange(vmin = 0.,    vmax = 1., value = .5,   inc = .1)
    speed     = DAQAttrRange(vmin = 0.125, vmax = 1., value = .125, inc = .1)

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def new(self, **kwa) -> DAQManual:
        "return a new daq protocol"
        newval = DAQManual(zmag      = self.zmag.value,
                           speed     = self.speed.value,
                           framerate = self.framerate)
        for i, j in kwa.items():
            setattr(newval, i, j)
        return newval

PROTOCOL = TypeVar('PROTOCOL', bound = Union[DAQProtocol, 'DAQManualConfig'])

def _strbody(theme, body: Tuple[Tuple[str,...]]) -> str:
    first = (f"<div><p style='margin: 0px; width:{theme.firstwidth}px;'><b>"
             +"{}</b>{}</p></div>")
    txt   = ""
    for i in body:
        if '(' in i[0]:
            ind  = i[0].rfind('(')
            txt +=  "<div class='dpx-span'>" + first.format(i[0][:ind], i[0][ind:])
        else:
            txt +=  "<div class='dpx-span'>" + first.format(i[0], '')
        txt += ''.join(f"<div><p style='margin: 0px;'>{j}</p></div>" for j in i[1:])
        txt += '</div>'
    return txt


class BaseProtocolButton(Generic[PROTOCOL]):
    "A button to access the modal dialog"
    _model: Union[DAQProtocol, DAQManualConfig]
    _theme: DAQProtocolTheme
    def observe(self, ctrl) -> bool:
        "observe the controller"
        if self._theme not in ctrl.theme:
            ctrl.theme.add(self._theme)
            ctrl.theme.add(self._model)
            ctrl.daq.observe(partial(self._onupdateprotocol, ctrl))
            return False
        return True

    def addtodoc(self, ctrl, doc, tbar, name):
        "add action to the toolbar"
        transient = deepcopy(self._model)

        @contextmanager
        def _context(_):
            yield
            diff = transient.diff(self._model)
            with ctrl.action:
                if diff:
                    ctrl.theme.update(self._model, **diff)
                self._context(ctrl, transient, diff)

        def _onclick_cb(attr, old, new):
            "method to trigger the modal dialog"
            transient.__dict__.update(deepcopy(self._model.__dict__))
            return dialog(doc,
                          context = _context,
                          title   = self._theme.title,
                          body    = _strbody(self._theme, self._body(ctrl)),
                          model   = transient,
                          always  = True)
        tbar.on_change(name, _onclick_cb)

    @staticmethod
    @abstractmethod
    def _context(ctrl, transient, diff):
        pass

    @abstractmethod
    def _body(self, ctrl) -> Tuple[Tuple[str,...]]:
        pass

    @abstractmethod
    def _onupdateprotocol(self, ctrl, model = None, **_):
        pass

class ProtocolButton(BaseProtocolButton[PROTOCOL]):
    "A button to access the modal dialog"
    _model: DAQProtocol
    _TITLE: ClassVar[str]
    def __init__(self, **kwa):
        self._model = templateattribute(self, 0)(**kwa)
        self._theme = DAQProtocolTheme(name  = "daq."+self._model.name,
                                       title = self._TITLE,
                                       **kwa)

    def _onupdateprotocol(self, ctrl, model = None, **_):
        if model.name == self._model.name:
            ctrl.theme.update(self._model, **model.diff(self._model))

    @staticmethod
    def _context(ctrl, transient, _):
        ctrl.daq.updateprotocol(deepcopy(transient))

    def _body(self, ctrl) -> Tuple[Tuple[str, ...]]:
        mdl = self._model
        dfl = ctrl.theme.model(self._model, True)

        cnt = list(self._theme.body[0])
        if mdl.cyclecount != dfl.cyclecount:
            cnt = [cnt[0]+f" ({dfl.cyclecount})", cnt[1]]
        fra = list(self._theme.body[1])
        if mdl.framerate != dfl.framerate:
            fra = [fra[0]+f" ({dfl.framerate})", fra[1]]

        assert len(mdl.phases) == len(dfl.phases)

        body = [cnt, fra, *(i for i in self._theme.body[2:-1])]
        for i, j in enumerate(dfl.phases):
            body.append([j.format(index = i) for j in self._theme.body[-1]])
            if j != mdl.phases[i]:
                body[-1][0] += f' ({round(j.zmag,3)}, {round(j.speed,3)}, {round(j.duration,3)})'

        return cast(Tuple[Tuple[str, ...]], tuple(tuple(i) for i in body))

class DAQProbeButton(ProtocolButton[DAQProbe]):
    "View the DAQProbe"
    _TITLE: ClassVar[str] = "Probe Settings"

class DAQRampButton(ProtocolButton[DAQRamp]):
    "View the DAQRamp"
    _TITLE: ClassVar[str] = "Ramp Settings"

class DAQManualButton(BaseProtocolButton[DAQManualConfig]):
    "View the DAQ Manual tools"
    _model: DAQManualConfig
    _TITLE = "Manual Settings"
    _BODY  = [["Frame rate", "%(framerate)d"],
              ["Bead ROI",  "width/height"],
              ["", "%(roi[2])d", "%(roi[3])d"],
              ["", "min / max / increment"],
              ["Zmag",  *(f'%(zmag.{i}).3f'  for i in ('vmin', 'vmax', 'inc'))],
              ["Speed", *(f'%(speed.{i}).3f' for i in ('vmin', 'vmax', 'inc'))]]
    def __init__(self, **kwa):
        self._model = DAQManualConfig(**kwa)
        self._theme = DAQProtocolTheme(name  = "daq."+self._model.name,
                                       body  = self._BODY,
                                       title = self._TITLE,
                                       **kwa)

    def observe(self, ctrl) -> bool:
        "observe the controller"
        if super().observe(ctrl):
            return True

        ctrl.theme  .updatedefaults('keystroke', zmagup   = 'Shift-Z', zmagdown = 'z')
        ctrl.display.updatedefaults('keystroke',
                                    zmagup   = lambda: self._onkeyzmag(ctrl, True),
                                    zmagdown = lambda: self._onkeyzmag(ctrl, False))

        @ctrl.theme.observe("daqmanual", "addedaqmanual")
        def _ontheme(**_):
            if self._model.roi[2:] != list(ctrl.daq.config.defaultbead.roi[2:]):
                ctrl.daq.updatedefaultbead(roi = tuple(self._model.roi))
        return False

    def addtodoc(self, ctrl, doc, tbar, name):
        "bokeh stuff"
        super().addtodoc(ctrl, doc, tbar, name)

        def _on_cb(attr, old, new):
            if getattr(self._model, attr).value != new:
                with ctrl.action:
                    ctrl.daq.updateprotocol(self._model.new(**{attr: new}))
        tbar.on_change("zmag", _on_cb)

        @ctrl.theme.observe
        def _ondaqmanual(**_): # pylint: disable=unused-variable
            tbar.update(**self.addtodocargs(ctrl))

    def addtodocargs(self, _):
        "return args for the toolbar"
        mdl = self._model
        return dict(zmagmin  = mdl.zmag.vmin,   zmagmax  = mdl.zmag.vmax,
                    zmag     = mdl.zmag.value , zinc     = mdl.zmag.inc,
                    speedmin = mdl.speed.vmin,  speedmax = mdl.speed.vmax,
                    speed    = mdl.speed.value, speedinc = mdl.speed.inc)

    def _body(self, ctrl) -> Tuple[Tuple[str, ...]]:
        body = deepcopy(self._theme.body)
        dfl  = ctrl.theme.model(self._model, True)

        if self._model.framerate != dfl.framerate:
            body[0][0] += f" ({dfl.framerate})"

        if self._model.roi != dfl.roi:
            body[2][0] += f" ({dfl.roi[2]}, {dfl.roi[3]})"

        for line, attr in zip(body[-2:], ('zmag', 'speed')):
            val = getattr(dfl, attr)
            if getattr(self._model, attr) != val:
                line[0] += f" ({round(val.vmin, 3)} / {round(val.vmax, 3)} / {round(val.inc,3)})"

        return cast(Tuple[Tuple[str, ...]], tuple(tuple(i) for i in body))

    @staticmethod
    def _context(ctrl, transient, diff):
        if 'roi' in diff:
            ctrl.daq.updatedefaultbead(roi = tuple(transient.roi))
        ctrl.daq.updateprotocol(transient.new())

    def _onupdateprotocol(self, ctrl, model = None, **_):
        if not model.ismanual():
            return

        zmag        = deepcopy(self._model.zmag)
        zmag.value  = model.zmag
        speed       = deepcopy(self._model.speed)
        speed.value = model.speed
        ctrl.theme.update(self._model,
                          framerate = model.framerate,
                          zmag      = zmag,
                          speed     = speed)

    def _onkeyzmag(self, ctrl, moveup):
        zmag = self._model.zmag.move(moveup)
        if zmag != self._model.zmag.value:
            ctrl.daq.updateprotocol(self._model.new(zmag = zmag))

class DAQNetworkButton:
    "View the DAQ Manual tools"
    _TITLE = "Network Settings"
    _BODY  = [["Commands",  "%(websocket)250s"],
              ["Data feeds",
               "<p style='width: 250px'>address</p>",
               "<p style='width: 80px'>port</p>",
               "<p style='width: 120px'>multicast</p>"],
              ["Teensy", "%(fov.address[0])250s",   "%(fov.address[1])d",
               "%(fov.multicast)120s"],
              ["Bead",   "%(beads.address[0])250s", "%(beads.address[1])d",
               "%(beads.multicast)120s"]]
    def __init__(self, **kwa):
        self._theme = DAQProtocolTheme(name       = "daq.network",
                                       body       = self._BODY,
                                       title      = self._TITLE,
                                       firstwidth = 120, **kwa)
    @staticmethod
    def _model(ctrl):
        return ctrl.daq.config.network

    def _body(self, ctrl) -> Tuple[Tuple[str, ...]]:
        mdl = self._model(ctrl)
        dfl = ctrl.theme.model(self._model, True)

        cnt = list(self._theme.body[0])
        if mdl.cyclecount != dfl.cyclecount:
            cnt = [cnt[0]+f" ({dfl.cyclecount})", cnt[1]]
        fra = list(self._theme.body[1])
        if mdl.framerate != dfl.framerate:
            fra = [fra[0]+f" ({dfl.framerate})", fra[1]]

        assert len(mdl.phases) == len(dfl.phases)

        body = [cnt, fra, *(i for i in self._theme.body[2:-1])]
        for i, j in enumerate(dfl.phases):
            body.append([j.format(index = i) for j in self._theme.body[-1]])
            if j != mdl.phases[i]:
                body[-1][0] += f' ({round(j.zmag,3)}, {round(j.speed,3)}, {round(j.duration,3)})'

        return cast(Tuple[Tuple[str, ...]], tuple(tuple(i) for i in body))

    def observe(self, ctrl):
        "observe the controller"
        if self._theme not in ctrl.theme:
            ctrl.theme.add(self._theme)

    def addtodoc(self, ctrl, doc, tbar, name):
        "add action to the toolbar"
        transient = deepcopy(self._model(ctrl))

        @contextmanager
        def _context(_):
            yield
            diff = transient.diff(self._model(ctrl))
            if diff:
                with ctrl.action:
                    vals = ctrl.daq.data.fovstarted, ctrl.daq.data.beadsstarted
                    ctrl.daq.listen(False, False)
                    ctrl.daq.updatenetwork(**diff)
                    ctrl.daq.listen(*vals)

        def _onclick_cb(attr, old, new):
            "method to trigger the modal dialog"
            transient.__dict__.update(deepcopy(self._model(ctrl).__dict__))
            return dialog(doc,
                          context = _context,
                          title   = self._theme.title,
                          body    = _strbody(self._theme, self._theme.body),
                          model   = transient,
                          always  = True)
        tbar.on_change(name, _onclick_cb)
