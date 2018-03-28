#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Set the protocol
"""
from abc                import abstractmethod
from copy               import deepcopy
from contextlib         import contextmanager
from typing             import Tuple, TypeVar, Generic, Union, cast

from utils              import initdefaults
from utils.inspection   import templateattribute
from utils.logconfig    import getLogger
from modaldialog        import dialog

from ..model            import DAQProtocol, DAQRamp, DAQProbe

LOGS   = getLogger(__name__)

class DAQProtocolTheme:
    "Basic theme for a modal dialog"
    name     = ""
    title    = ""
    width    = 90
    body     = [["Frame rate", "%(framerate)d"],
                ["Phase {index}",
                 "Zmag",     "%(phase[{index}].zmag)3of",
                 "speed",    "%(phase[{index}].speed)3of",
                 "duration", "%(phase[{index}].duration)of",
                ]]
    height   = 20
    @initdefaults
    def __init__(self, **_):
        pass

class DAQAttrRange:
    "attribute value and range"
    vmin   = 0.
    value  = .5
    vmax   = 1.
    inc    = .1
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

class DAQManualDisplay:
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

def _getbody(name):
    return (f'%({name}.vmin)f',
            "<",    f"%({name}.value)f",
            '<',    f"%({name}.vmax)f",
            "+/-",  f"%({name}.inc)")

class DAQManualTheme:
    """
    DAQ idle values
    """
    name = "daqmanual"
    body = [['Frame rate', '%(framerate)d'],
            ['Z mag',      *_getbody("zmag")],
            ['Speed',      *_getbody("speed")]
           ]

PROTOCOL = TypeVar('PROTOCOL', bound = Union[DAQProtocol, 'DAQManualDisplay'])

class ProtocolDisplay(Generic[PROTOCOL]):
    "Basic theme for a modal dialog"
    protocol: PROTOCOL
    def __init__(self, protocol):
        self.protocol: PROTOCOL = protocol
        self.name               = type(protocol).__name__.lower()

class BaseProtocolButton(Generic[PROTOCOL]):
    "A button to access the modal dialog"
    _model: PROTOCOL

    @abstractmethod
    def _body(self, ctrl) -> Tuple[Tuple[str, ...]]:
        pass

    @contextmanager
    @abstractmethod
    def _context(self, ctrl):
        pass


    def observe(self, ctrl):
        "observe the controller"
        if self._theme in ctrl.theme:
            return

        ctrl.theme.add(self._theme)
        ctrl.display.add(self._display)

        @ctrl.daq.observe
        def _onupdateprotocol(model = None, **_): # pylint: disable=unused-variable
            if type(model) is type(self._model):
                ctrl.display.update(self._display, *model.__dict__)

    def addtodoc(self, tbar, doc, ctrl, name):
        "add action to the toolbar"
        def _onclick_cb(attr, old, new):
            "method to trigger the modal dialog"
            self._model = deepcopy(self._display.protocol)
            return dialog(doc,
                          context = self._context(ctrl),
                          title   = self._theme.title,
                          body    = self._body(ctrl),
                          model   = self._model)
        tbar.on_change(name, _onclick_cb)

class ProtocolButton(BaseProtocolButton[PROTOCOL]):
    "A button to access the modal dialog"
    def __init__(self, **kwa):
        self._model   = templateattribute(self, 0)(**kwa)
        self._display = ProtocolDisplay[PROTOCOL](deepcopy(self._model))
        self._theme   = DAQProtocolTheme(name = self._display.name, **kwa)

    def _body(self, ctrl) -> Tuple[Tuple[str, ...]]:
        mdl = self._display.protocol
        dfl = ctrl.display.model(self._display, True).protocol

        fra = list(self._theme.body[0])
        if mdl.framerate != dfl.framerate:
            fra = [fra[0]+f" ({dfl.framerate})", fra[1]]

        assert len(mdl.phases) == dfl.phases

        body = [fra]
        for i, j in enumerate(dfl.phases):
            body.append([j.format(index = i) for j in self._theme.body[1]])
            if j.__dict__ != mdl.phases[i].__dict__:
                body[-1][0] += f' ({j.zmag}, {j.speed}, {j.duration})'

        return cast(Tuple[Tuple[str, ...]], tuple(tuple(i) for i in body))

    @contextmanager
    def _context(self, ctrl):
        yield

        cur  = self._display.protocol
        diff = {i:j for i, j in cur.__dict__.items() if j != getattr(self._model, i)}

        if diff:
            with ctrl.action():
                ctrl.display.update(cur, **diff)
        ctrl.daq.updateprotocol(cur)

class DAQProbeButton(ProtocolButton[DAQProbe]):
    "View the DAQProbe"

class DAQRampButton(ProtocolButton[DAQRamp]):
    "View the DAQRamp"

class DAQManualButton(BaseProtocolButton[DAQManualDisplay]):
    "View the DAQ Manual tools"
    def __init__(self, **kwa):
        self._model   = DAQManualDisplay(**kwa)
        self._display = deepcopy(self._model)
        self._theme   = DAQProtocolTheme(name = self._display.name, **kwa)

    def _body(self, ctrl) -> Tuple[Tuple[str, ...]]:
        body = deepcopy(self._theme.body)
        dfl  = ctrl.display.model(self._display, True)
        for line in body:
            val = line[1].split('(')[-1].split(')')[0]
            if getattr(self._display, val) != getattr(dfl, val):
                line[0] += f" ({getattr(dfl, val)})"

        return cast(Tuple[Tuple[str, ...]], tuple(tuple(i) for i in body))

    @contextmanager
    def _context(self, ctrl):
        yield

        cur  = self._display
        diff = {i:j for i, j in cur.__dict__.items() if j != getattr(self._model, i)}

        if diff:
            with ctrl.action():
                ctrl.display.update(cur, **diff)
        ctrl.daq.updateprotocol(cur)

    def addtodoc(self, tbar, doc, ctrl, name):
        "bokeh stuff"
        super().addtodoc(tbar, doc, ctrl, name)

        @ctrl.display.observe
        def _ondaqmanual(**_): # pylint: disable=unused-variable
            tbar.update(**self.addtodocargs(ctrl))

    def addtodocargs(self, _):
        "return args for the toolbar"
        return dict(zmagmin  = self.zmag.vmin,   zmagmax  = self.zmag.vmax,
                    zmag     = self.zmag.value , zinc     = self.zmag.inc,
                    speedmin = self.speed.vmin,  speedmax = self.speed.vmax,
                    speed    = self.speed.value, speedinc = self.speed.inc)
