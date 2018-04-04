#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Set the protocol
"""
from abc                import abstractmethod
from contextlib         import contextmanager
from copy               import deepcopy
from typing             import Tuple, TypeVar, Generic, Union, ClassVar, cast

from utils              import initdefaults
from utils.inspection   import templateattribute
from utils.logconfig    import getLogger
from modaldialog        import dialog

from ..model            import DAQProtocol, DAQRamp, DAQProbe, DAQManual, ConfigObject

LOGS   = getLogger(__name__)

class DAQProtocolTheme(ConfigObject):
    "Basic theme for a modal dialog"
    name     = ""
    title    = ""
    width    = 90
    body     = [["Frame rate", "%(framerate)d"],
                ["Phases", "Zmag / speed / duration"],
                ["{index}",
                 "%(phases[{index}].zmag).3of",
                 "%(phases[{index}].speed).3of",
                 "%(phases[{index}].duration)of",
                ]]
    firstwidth = 150
    height     = 20
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

class DAQManualDisplay(ConfigObject):
    """
    DAQ manual values
    """
    name      = "daqmanual"
    framerate = 30
    zmag      = DAQAttrRange(vmin = 0.,    vmax = 1., value = .5,   inc = .1)
    speed     = DAQAttrRange(vmin = 0.125, vmax = 1., value = .125, inc = .1)

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

PROTOCOL = TypeVar('PROTOCOL', bound = Union[DAQProtocol, 'DAQManualDisplay'])

class ProtocolDisplay(Generic[PROTOCOL]):
    "Basic theme for a modal dialog"
    protocol: PROTOCOL
    def __init__(self, protocol):
        self.protocol: PROTOCOL = protocol
        self.name               = type(protocol).__name__.lower()

class BaseProtocolButton(Generic[PROTOCOL]):
    "A button to access the modal dialog"
    _model:   PROTOCOL
    _display: Union[ProtocolDisplay[PROTOCOL], DAQManualDisplay]
    _theme:   DAQProtocolTheme

    @abstractmethod
    def _body(self, ctrl) -> Tuple[Tuple[str,...]]:
        pass

    def _strbody(self, body: Tuple[Tuple[str,...]]) -> str:
        theme = self._theme
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

    @property
    @abstractmethod
    def _protocol(self):
        pass

    @staticmethod
    @abstractmethod
    def _context(cur):
        pass

    def observe(self, ctrl):
        "observe the controller"
        if self._theme not in ctrl.theme:
            ctrl.theme.add(self._theme)
            ctrl.display.add(self._display)

    def addtodoc(self, ctrl, doc, tbar, name):
        "add action to the toolbar"
        @contextmanager
        def _context(_):
            yield
            cur  = self._protocol
            diff = cur.diff(self._model)
            if diff:
                with ctrl.action():
                    ctrl.display.update(cur, **diff)
            ctrl.daq.updateprotocol(self._context(cur))

        def _onclick_cb(attr, old, new):
            "method to trigger the modal dialog"
            self._model = deepcopy(self._protocol)
            return dialog(doc,
                          context = _context,
                          title   = self._theme.title,
                          body    = self._strbody(self._body(ctrl)),
                          model   = self._model,
                          always  = True)
        tbar.on_change(name, _onclick_cb)

class ProtocolButton(BaseProtocolButton[PROTOCOL]):
    "A button to access the modal dialog"
    _display: ProtocolDisplay[PROTOCOL]
    _TITLE  : ClassVar[str]
    def __init__(self, **kwa):
        self._model   = templateattribute(self, 0)(**kwa)
        self._display = ProtocolDisplay[PROTOCOL](deepcopy(self._model))
        self._theme   = DAQProtocolTheme(name  = self._display.name,
                                         title = self._TITLE,
                                         **kwa)

    def observe(self, ctrl):
        "observe the controller"
        if self._theme in ctrl.theme:
            return
        super().observe(ctrl)

        @ctrl.daq.observe
        def _onupdateprotocol(model = None, **_): # pylint: disable=unused-variable
            if type(model) is type(self._model):
                ctrl.display.update(self._display, protocol = model)

    @property
    def _protocol(self):
        return self._display.protocol

    def _body(self, ctrl) -> Tuple[Tuple[str, ...]]:
        mdl = self._display.protocol
        dfl = ctrl.display.model(self._display, True).protocol

        fra = list(self._theme.body[0])
        if mdl.framerate != dfl.framerate:
            fra = [fra[0]+f" ({dfl.framerate})", fra[1]]

        assert len(mdl.phases) == len(dfl.phases)

        body = [fra, *(i for i in self._theme.body[:-1])]
        for i, j in enumerate(dfl.phases):
            body.append([j.format(index = i) for j in self._theme.body[-1]])
            if j != mdl.phases[i]:
                body[-1][0] += f' ({j.zmag}, {j.speed}, {j.duration})'

        return cast(Tuple[Tuple[str, ...]], tuple(tuple(i) for i in body))

    @staticmethod
    def _context(cur):
        return cur

class DAQProbeButton(ProtocolButton[DAQProbe]):
    "View the DAQProbe"
    _TITLE: ClassVar[str] = "Probe Settings"

class DAQRampButton(ProtocolButton[DAQRamp]):
    "View the DAQRamp"
    _TITLE: ClassVar[str] = "Ramp Settings"

class DAQManualButton(BaseProtocolButton[DAQManualDisplay]):
    "View the DAQ Manual tools"
    _display: DAQManualDisplay
    _TITLE = "Manual Settings"
    _BODY  = [["Frame rate", "%(framerate)d"],
              ["", "min / max / increment"],
              ["Zmag",  *(f'%(zmag.{i}).3f'  for i in ('vmin', 'vmax', 'inc'))],
              ["Speed", *(f'%(speed.{i}).3f' for i in ('vmin', 'vmax', 'inc'))]]
    def __init__(self, **kwa):
        self._model   = DAQManualDisplay(**kwa)
        self._display = deepcopy(self._model)
        self._theme   = DAQProtocolTheme(name  = self._display.name,
                                         body  = self._BODY,
                                         title = self._TITLE,
                                         **kwa)

    def _body(self, ctrl) -> Tuple[Tuple[str, ...]]:
        body = deepcopy(self._theme.body)
        dfl  = ctrl.display.model(self._display, True)

        if self._display.framerate != dfl.framerate:
            body[0][0] += f" (dfl.framerate)"

        for line, attr in zip(body[1:], ('zmag', 'speed')):
            val = getattr(dfl, attr)
            if getattr(self._display, attr) != val:
                line[0] += f" ({val.vmin:.3f} / {val.vmax:.3f} / {val.inc:.3f})"

        return cast(Tuple[Tuple[str, ...]], tuple(tuple(i) for i in body))

    @staticmethod
    def _context(cur):
        return DAQManual(zmag = cur.zmag.value, speed = cur.speed.value)

    @property
    def _protocol(self):
        return self._display

    def observe(self, ctrl):
        "observe the controller"
        if self._theme in ctrl.theme:
            return
        super().observe(ctrl)

        @ctrl.daq.observe
        def _onupdateprotocol(model = None, **_): # pylint: disable=unused-variable
            if isinstance(model, DAQManual):
                zmag        = deepcopy(self._display.zmag)
                zmag.value  = model.zmag
                speed       = deepcopy(self._display.speed)
                speed.value = model.speed
                ctrl.display.update(self._display,
                                    framerate = model.framerate,
                                    zmag      = zmag,
                                    speed     = speed)

    def addtodoc(self, ctrl, doc, tbar, name):
        "bokeh stuff"
        super().addtodoc(ctrl, doc, tbar, name)

        @ctrl.display.observe
        def _ondaqmanual(**_): # pylint: disable=unused-variable
            tbar.update(**self.addtodocargs(ctrl))

    def addtodocargs(self, _):
        "return args for the toolbar"
        mdl = self._display
        return dict(zmagmin  = mdl.zmag.vmin,   zmagmax  = mdl.zmag.vmax,
                    zmag     = mdl.zmag.value , zinc     = mdl.zmag.inc,
                    speedmin = mdl.speed.vmin,  speedmax = mdl.speed.vmax,
                    speed    = mdl.speed.value, speedinc = mdl.speed.inc)
