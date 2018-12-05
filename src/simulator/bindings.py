#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simulates binding events"
from copy   import copy, deepcopy
from enum   import Enum
from typing import (Dict, Any, FrozenSet, Optional, List, Union, Iterable,
                    Sequence, NamedTuple, Tuple, cast)
import numpy  as np

RandState = Union[int, None, np.random.RandomState]

def randstate(seed: RandState = 0) -> np.random.RandomState:
    "return a random state"
    return seed if isinstance(seed, np.random.RandomState) else np.random.RandomState(seed)

class Object:
    """
    Auto-initialized object
    """
    _ARGS: FrozenSet[str] = frozenset()
    @staticmethod
    def args(locs)-> FrozenSet[str]:
        """
        Return current attributes
        """
        return frozenset([i for i in locs if i[0] not in ('_', i[0].upper())])

    def __init__(self, firstarg = None, **args):
        if isinstance(firstarg, self.__class__):
            itms = dict(firstarg.__dict__)
            itms.update(args)
            args = itms

        for i in self._ARGS & set(args):
            setattr(self, i, args[i])
        for i in self._ARGS - set(args):
            setattr(self, i, copy(getattr(self.__class__, i)))

class Phase(Sequence[int]):
    """
    Phase names in a cycle. Labeled phases are characterized by a stable magnet
    height.  Each of them is preceeded and followed by a phase where the magnet
    height is changed.

    The following describes the usual situation:

    * `initial`: phase 1 should be at the same magnet height (~10 pN of force) as
    `measure`. It could be used as a reference point.
    * `pull`: phase 3 is when the magnet is at the closest from the
    sample (18 pN of force). This is when a hairpin should unzip.
    * `measure`: phase 5 is when hybridisation events are measured (10 pN of force).
    * `relax`: phase 7 is used to remove probes from the hairpin.  The magnet
    is then at its farthest point (5 pN of force).
    """
    toinitial = 0
    initial   = 1
    rampup    = 2
    pull      = 3
    rampdown  = 4
    measure   = 5
    torelax   = 6
    relax     = 7
    length    = 8
    durations = [5, 20, 5, 20, 60, 400, 5, 20]
    def __init__(self, durations = None, **_):
        super().__init__()
        self.durations = (copy(self.__class__.durations) if durations is None else
                          durations)

    def __getitem__(self, i):
        if isinstance(i, (list, np.ndarray)):
            return [self[j] for j in i]
        if isinstance(i, str):
            return self.durations[getattr(self, i)]
        return self.durations[i]

    def __setitem__(self, i, j):
        if isinstance(i, str):
            i = getattr(self, i)
        self.durations[i] = j

    def __iter__(self):
        return iter(self.durations)

    def __len__(self):
        return len(self.durations)

    def indexes(self, *names) -> np.ndarray:
        "return the phase indexes from phase 0"
        inds = np.cumsum(np.insert(self.durations, 0, 0))
        if len(names) == 0:
            return inds
        return inds[[getattr(self, i) for i in names]]

class Nature(Enum):
    """
    The nature of a binding
    """
    probe        = 'probe'
    structural   = 'structural'
    singlestrand = 'singlestrand'
    spurious     = 'spurious'

class _EnumDescriptor:
    __slots__ = ('name', 'default')
    def __init__(self, default: Enum) -> None:
        self.name    = None
        self.default = default

    def __set_name__(self, _, name):
        self.name = name

    def __get__(self, inst, owner) -> str:
        return inst.__dict__[self.name] if inst is not None else self.default.name

    def __set__(self, inst, value: Union[Enum, str]):
        inst.__dict__[self.name] = type(self.default)(value).name

class Binding(Object):
    """
    A binding's characteristics
    """
    position: float
    nature          = cast(str, _EnumDescriptor(Nature.probe))
    onrate  : float = 1.
    offrate : float = 0.
    _ARGS  = Object.args(set(locals()) | {'position'})
    def __init__(self, position, **kwa):
        super().__init__(position = position, **kwa)

class ThermalDrift:
    """
    Add thermal drift to each cycle
    """
    tscale = 30.
    zscale = 1e-2
    def __call__(self, cnf:'Experiment', bead, _ = None):
        if None in (self.tscale, self.zscale):
            return None
        inds = cnf.phases.indexes('rampup', 'rampdown', 'torelax', 'length')
        size = inds[1]-inds[0]

        driftup    = np.exp((np.arange(size)-size+1)/self.tscale)
        driftup   -= driftup[0]
        driftup   *= self.zscale/driftup[-1]

        driftdown  = np.exp(-np.arange(inds[2]-inds[1])/self.tscale)
        driftdown -= driftdown[-1]
        driftdown *= driftup[-1]/driftdown[0]

        drift                   = np.zeros(inds[-1], dtype = 'f4')
        drift[inds[0]:inds[1]] += driftup
        drift[inds[1]:inds[2]] += driftdown

        if bead is not None:
            bead[:].reshape((-1, drift.size))[:] += drift
        return drift

class KneedBaseline(Object):
    """
    Add baseline to bead
    """
    sigma = 5e-3
    knee  = 30./1e3
    alpha = 1.
    _ARGS = Object.args(locals())
    def __call__(self, cnf: 'Experiment', seed = None):
        size    = cnf.ncycles * np.sum(cnf.phases)+1
        #generate white noise in time domain
        #shaping in freq domain
        fft     = getattr(np, 'fft')
        signal  = fft.rfft(randstate(seed).normal(0., self.sigma, size))
        tmp     = fft.fftfreq(size, d=1.)[:len(signal)]
        tmp[-1] = np.abs(tmp[-1])

        # set mean to 0.
        signal[0]     = 0.

        good          = np.logical_and(tmp < self.knee, tmp != 0.)
        signal[good] *= np.abs((tmp[good]/self.knee)**(-self.alpha))

        # discard high-freq amplitudes
        signal[tmp>self.knee] = 0.
        out                   = fft.irfft(signal)
        assert len(out) >= size
        return out[:size-1]

class Baseline(Object):
    """
    Add baseline to bead
    """
    sigma     = 3e-3
    framerate = 30.
    params    = [1.089, 2.444]
    covar     = [[.01, .005], [.005,.04]]
    _ARGS     = Object.args(locals())

    def shape(self, params, size) -> np.ndarray:
        "return the shape in the frequency domain: the spectral power density"
        shape    = np.linspace(1., self.framerate/2.+1., size)
        shape    = np.exp(params[0]-params[1]*np.log(shape))
        shape    = np.exp(shape-shape[0])
        shape[0] = 0
        return shape

    def randparams(self, rand) -> np.ndarray:
        "return the random parameters"
        return (rand.multivariate_normal(self.params, self.covar) if self.covar else
                self.params)

    def __call__(self, cnf: Union[int,'Experiment'], seed = None) -> np.ndarray:
        size    = (cnf if isinstance(cnf, int ) else cnf.ncycles * np.sum(cnf.phases))+1
        rand    = randstate(seed)

        signal  = np.fft.rfft(rand.normal(0., 1., size))
        signal *= self.shape(self.randparams(rand), signal.size)
        signal  = np.fft.irfft(signal)[:size-1]

        diff    = np.diff(signal)
        signal *= self.sigma/np.median(np.abs(diff-np.median(diff)))

        return signal

class StrandClosingTruth(NamedTuple):
    duration: np.ndarray
    delta:    np.ndarray

class StrandClosing(Object):
    """
    Add a closing of the strand in phase 4
    """
    start = 40
    mean  = 3
    _ARGS = Object.args(locals())
    def __call__(self,
                 cnf: 'Experiment',
                 base: np.ndarray,
                 seed: RandState = None) -> StrandClosingTruth:
        rnd    = randstate(seed)
        inds   = cnf.phases.indexes('rampdown', 'measure')
        frames = self.start + np.int32(rnd.poisson(self.mean, cnf.ncycles))+inds[0]

        delta  = base[:,inds[1]]-base[:,inds[1]-1]
        delta -= (base[:,inds[1]-1]-base[:,inds[0]])/(inds[1]-1-inds[0])

        # make sure that no closing occurs for single strand events
        frames[delta > -5e-6] = inds[1]

        # sanity check
        frames = np.clip(frames, inds[0], inds[1])

        # deltas for non closing cycles
        delta[frames == inds[1]] = 0.

        for i, j, k in zip(frames, delta, base):
            k[i:inds[1]] += j
        return StrandClosingTruth(frames, delta)

class BrownianMotion(Object):
    "Deals with brownian motion"
    sigma: Optional[float] = 2.e-3
    pullfactor             = .8
    relaxfactor            = 1.6
    walk                   = False
    _ARGS                  = Object.args(locals())
    def __init__(self, sigma: float = None, **kwa) -> None:
        super().__init__(**kwa, **({'sigma': sigma} if sigma is not None else {}))

    def phasesigma(self, val)-> float:
        "phase 3 extension"
        if self.sigma is None:
            return 0.
        return  (self.sigma*self.pullfactor  if val == 3            else
                 self.sigma*self.relaxfactor if val == 0 or val > 6 else
                 self.sigma)

    def __call__(self,
                 cnf   : 'Experiment',
                 events: np.ndarray = None,
                 seed  : RandState = None) -> np.ndarray:
        """
        Add brownian motion
        """
        if not self.sigma:
            return np.zeros((0, 0), dtype = 'f4')

        noise = randstate(seed).normal
        if events is None:
            brown  = noise(0., self.sigma, (cnf.ncycles, len(cnf.positions)))
            brown += cnf.positions
            return brown
        if len(events.shape) == 1 or events.shape[1] == len(cnf.bindings):
            brown = noise(0., self.sigma, events.shape)
        else:
            brown   = np.zeros(events.shape, dtype = 'f4')
            inds    = cnf.phases.indexes('initial', 'pull', 'measure', 'relax', 'length')
            size    = cnf.ncycles

            brown[:,:inds[0]]        += noise(0., self.phasesigma(7), (size, inds[0]))
            brown[:,inds[0]:inds[1]] += noise(0., self.phasesigma(1), (size, inds[1]-inds[0]))
            brown[:,inds[1]:inds[2]] += noise(0., self.phasesigma(3), (size, inds[2]-inds[1]))
            brown[:,inds[2]:inds[3]] += noise(0., self.phasesigma(5), (size, inds[3]-inds[2]))
            brown[:,inds[3]:]        += noise(0., self.phasesigma(7), (size, inds[4]-inds[3]))

        if self.walk:
            brown = np.cumsum(brown, axis = 1)
        events += brown
        return events

class _BindingAttribute:
    __slots__        = ('name', 'dtype')
    NAMES: List[str] = []
    def __init__(self, dtype = 'f4'):
        self.name  = None
        self.dtype = np.dtype(dtype)

    def __set_name__(self, _, name):
        assert name[-1] == 's'
        self.name = name[:-1]
        self.NAMES.append(name)

    def __get__(self, inst, owner):
        name = self.name
        return tuple(getattr(owner, name) if inst is None else
                     (getattr(i, name) for i in inst.bindings))

    def __set__(self, inst, val):
        if np.isscalar(val) or isinstance(val, str):
            val = np.full(len(inst.bindings), val, dtype = self.dtype)
        name = self.name
        for bind, itm in zip(inst.bindings, val):
            setattr(bind, name, itm)

    @classmethod
    def update(cls, inst, kwa):
        "set attributes"
        for i in cls.NAMES:
            if i in kwa:
                setattr(inst, i, kwa[i])

class _BehaviourDescriptor:
    __slots__ = ('name', 'default')
    def __init__(self, default: type) -> None:
        self.name    = None
        self.default = default
        assert isinstance(default, type)

    def __set_name__(self, _, name):
        self.name = name

    def __get__(self, inst, owner):
        return self.default if inst is None else  inst.__dict__[self.name]

    def __set__(self, inst, val):
        # pylint: disable=not-callable
        inst.__dict__[self.name] = (self.default()      if val is True           else
                                    self.default(val)   if np.isscalar(val)      else
                                    self.default(**val) if isinstance(val, dict) else
                                    val()               if isinstance(val, type) else
                                    val)

class _BindingsDescriptor:
    def __init__(self) -> None:
        self.name    = None
        self.default = [Binding(1., nature = 'singlestrand', onrate = .2, offrate = 30),
                        .8, .5, .2, .1]

    def __set_name__(self, _, name):
        self.name = name

    def __get__(self, inst, owner):
        return self.default if inst is None else  inst.__dict__[self.name]

    @staticmethod
    def create(val: Union[Binding, Dict[str, Any], float]) -> Binding:
        "return a binding"
        return (Binding(val) if np.isscalar(val)         else
                val          if isinstance(val, Binding) else
                Binding(**cast(dict, val)))

    def __set__(self, inst, val: Iterable[Union[Binding, Dict[str, Any], float]]):
        inst.__dict__[self.name] = [self.create(i) for i in val]

class _SingleStrandBinding:
    SINGLE_STRAND_FACTOR  = 1.1
    def __get__(self, inst, owner):
        "return the single strand binding"
        if inst is None:
            return self

        name = Nature.singlestrand.name
        val  = next((i for i in inst.bindings if i.nature == name), None)
        if val is None:
            return Binding(max(inst.positions)*self.SINGLE_STRAND_FACTOR,
                           onrate   = 0.,
                           offrate  = 0.,
                           nature   = Nature.singlestrand)
        return val

    def __set__(self, inst, value):
        "set the single strand binding"
        val = _BindingsDescriptor.create(value)
        ind = next((i for i, j in enumerate(inst.bindings) if j.nature == Nature.singlestrand),
                   None)
        if ind is not None:
            inst.bindings.insert(0, val)
        else:
            inst.bindings[ind] = val

class BeadTruth(NamedTuple):
    strandclosing: Optional[StrandClosingTruth]
    events:        Optional[np.ndarray]
    baseline:      Optional[np.ndarray]
    drift:         Optional[np.ndarray]

class Experiment(Object):
    """
    Information on the experiment

    # Attributes

    * `ncycles` length of cycles
    * `bindings` list of bindings, their position and nature
    * `pullfactor` is the amount by which a binding position is increased in `phase.pull`
    * `phases` is the names and durations of phases
    * `brownianmotion` adds gaussian noise to the data unless set to None
    * `strandclosing` simulates the strand closing during `phase.rampdown`
    * `baseline` adds long term (>> frame) noise (as opposed to `brownianmotion`)
    * `thermaldrift` add cycle-periodic noise.

    # Properties

    Bindings attributes can be accessed as arrays.
    """
    ncycles        = 100
    bindings       = cast(List[Binding], _BindingsDescriptor())
    pullfactor     = 1.1
    phases         = Phase()
    brownianmotion = cast(BrownianMotion, _BehaviourDescriptor(BrownianMotion))
    strandclosing  = cast(StrandClosing,  _BehaviourDescriptor(StrandClosing))
    baseline       = cast(Baseline,       _BehaviourDescriptor(Baseline))
    thermaldrift   = cast(ThermalDrift,   _BehaviourDescriptor(ThermalDrift))
    fixedbeadsize  = .1
    _ARGS          = Object.args(locals())

    positions      = cast(Sequence[float],           _BindingAttribute())
    onrates        = cast(Sequence[Optional[float]], _BindingAttribute())
    offrates       = cast(Sequence[Optional[float]], _BindingAttribute())
    natures        = cast(Sequence[str],             _BindingAttribute('<U16'))
    singlestrand   = cast(Binding,                   _SingleStrandBinding())
    def __init__(self, **kwa):
        if 'positions' in kwa and "bindings" not in kwa:
            kwa['bindings'] = kwa.pop('positions')
        super().__init__(**kwa)
        _BindingAttribute.update(self, kwa)

    @property
    def npbindings(self) -> np.ndarray:
        "return binding positions & on/off rates in a single np.ndarray"
        return np.array(list(zip(self.positions, self.onrates, self.offrates)),
                        dtype = [('pos', 'f4'), ("on", 'f4'), ('off', 'f4')])

    def setup(self, **kwa):
        "reset *all* attributes"
        self.__init__(**kwa)

    def eventpositions(self, seed: RandState = None) -> np.ndarray:
        """
        Creates events positions
        """
        if self.brownianmotion is None:
            evts  = np.zeros((self.ncycles, len(self.positions)), dtype = 'f4')
            evts += self.positions
            return evts
        return self.brownianmotion(self, seed = seed)

    def eventdurations(self, seed: RandState = None) -> np.ndarray:
        """
        Creates events using provided positions, rates and durations.
        """
        rnd   = randstate(seed)
        shape = (self.ncycles, len(self.positions))
        ron   = rnd.rand(*shape) < self.onrates

        vals  = np.asarray(self.offrates)
        roff  = np.empty(shape, dtype = 'f4')
        if np.any(vals <= 0.):
            roff[:,vals <= 0.] = self.phases['measure']//(len(self.positions)+1)
        if np.any(vals > 0.):
            good         = vals > 0.
            roff[:,good] = rnd.poisson(vals[good], size = (shape[0], np.sum(good)))

        roff[~ron] = 0.
        roff[np.cumsum(roff, axis = 1) > self.phases['measure']] = 0.
        return roff

    def events(self, seed: RandState = None) -> np.ndarray:
        "return a list of event data"
        durs = self.eventdurations(seed = seed)

        data = np.zeros(int(np.sum(durs)), dtype = 'f4')
        if self.brownianmotion:
            self.brownianmotion(self, data, seed = seed)

        evts = np.array(np.split(data, np.cumsum(durs).ravel().astype(int)))[:-1]
        npos = len(self.positions)
        pos  = self.positions
        for i,j in enumerate(pos):
            evts[i::npos]+=j

        # # start of each event
        # starts = np.hstack([np.zeros((len(durs),1)),np.apply_along_axis(np.cumsum,1,durs[:,:-1])])
        # starts = starts.astype(int)

        # return [[(u,v) for u,v in zip(starts[i],j) if len(v)]
        #         for i,j in enumerate(evts.reshape(-1,npos))]
        return [[k for k in j if len(k)] for j in evts.reshape(-1,npos)]

    def fixedbead(self,
                  drift: np.ndarray = None,
                  base:  np.ndarray = None,
                  seed:  RandState  = None
                 ) -> Tuple[BeadTruth, np.ndarray]:
        """
        create one fixed bead data
        """
        return self.__bead(None, drift, base, seed, True)

    def bead(self,
             evts:  np.ndarray = None,
             drift: np.ndarray = None,
             base:  np.ndarray = None,
             seed:  RandState  = None,
            ) -> Tuple[BeadTruth, np.ndarray]:
        """
        create one bead data
        """
        return self.__bead(evts, drift, base, seed, False)

    def track(self,
              nbeads: int       = 1,
              nfixed: int       = 0,
              seed:   RandState = None,
              **kwa) -> Dict[str, Any]:
        """
        creates a track
        """
        rnd    = randstate(seed)

        base   = (self.baseline    (self, rnd)      if callable(self.baseline) else
                  np.zeros(self.ncycles*self.phases.indexes('length')[0], dtype = 'f4'))
        drift  = self.thermaldrift(self, base, rnd) if callable(self.baseline) else None

        itms   = [self.bead(..., drift, base, rnd) for i in range(nbeads)]
        itms  += [self.fixedbead(drift, base, rnd) for i in range(nfixed)]
        ends   = np.repeat([self.phases], self.ncycles, axis = 0).cumsum()
        phases = np.insert(ends, 0, 0)[:-1].reshape((self.ncycles, len(self.phases)))

        kwa.setdefault('framerate', 30.)
        kwa.setdefault('key',      'sim')
        kwa.update(data   = dict((i, j[1]) for i, j in enumerate(itms)),
                   truth  = dict((i, j[0]) for i, j in enumerate(itms)),
                   phases = phases.astype('i4'))
        return kwa

    def __bead(self, # pylint: disable=too-many-arguments
               evts:  np.ndarray = None,
               drift: np.ndarray = None,
               base:  np.ndarray = None,
               seed:  RandState  = None,
               fixed: bool       = False
              ) -> Tuple[BeadTruth, np.ndarray]:
        """
        create one bead data
        """
        rnd  = randstate(seed)
        if fixed:
            evts = None
        elif evts is None or evts is Ellipsis:
            evts = self.eventdurations(rnd)
        bead    = self.__beadstructure(evts, fixed)
        closing = (self.strandclosing(self, bead, rnd)
                   if not fixed and self.strandclosing else None)

        if self.brownianmotion:
            self.brownianmotion(self, bead, rnd)

        base  = (base                     if base is not None        else
                 self.baseline(self, rnd) if callable(self.baseline) else
                 np.zeros(bead.size, dtype = 'f4'))

        if drift is None and callable(self.thermaldrift):
            base  = np.copy(base)
            drift = self.thermaldrift(self, base, rnd)

        if base is not None:
            bead.ravel()[:] += base

        return BeadTruth(closing, evts, base, drift), bead.ravel()

    def __beadstructure(self, events: Optional[np.ndarray], fixed: bool) -> np.ndarray:
        """
        create bead data from events.

        This does not include any type of noise
        """
        inds    = self.phases.indexes()
        base    = np.zeros((self.ncycles, inds[-1]), dtype = 'f4')

        def _lin(first, sec, phase):
            size = self.phases[phase]
            return ((sec-first)*(np.arange(size)/(size+1)+1./(size+1.))[:,None] + first).T

        for i in (self.phases.initial, self.phases.pull, self.phases.relax):
            base[:,inds[i]:inds[i+1]] = self.__phasez(i, fixed)

        base[:,inds[0]:inds[1]] = _lin(self.__phasez(7, fixed),  base[:, inds[1]], 0)
        base[:,inds[2]:inds[3]] = _lin(base[:,inds[2]-1], base[:, inds[3]], 2)
        base[:,inds[4]:inds[5]] = _lin(base[:,inds[4]-1], self.__phasez(4, fixed), 4)
        base[:,inds[6]:inds[7]] = _lin(base[:,inds[6]-1], base[:, inds[7]], 6)

        if events is not None and len(events) and len(self.positions):
            pos = self.positions
            for vect, evts in zip(base[:, inds[5]:inds[6]], np.cumsum(np.int32(events), axis = 1)):
                vect[:evts[0]] = pos[0]
                for i, j in enumerate(pos[1:]):
                    vect[evts[i]:evts[i+1]] = j

        return base

    def __phasez(self, val, fixed)-> float:
        "phase 3 extension"
        if val == 1:
            return 0.
        if val == 3:
            return (self.fixedbeadsize if fixed else
                    self.singlestrand.position)*self.pullfactor
        if val == 4:
            return self.fixedbeadsize if fixed else self.singlestrand.position
        return -.1

class ExperimentCreator(Object):
    """
    Create random experiments & images
    """
    imgclip   = 20
    nbindings = np.arange(0, 11)
    bins      = [1000, .5e-3]
    size      = (.2, (bins[0]-10)*bins[1])
    onrates   = [.05, .5]
    offrates  = [3, 30]
    template  = Experiment()
    _ARGS     = Object.args(locals())
    def experiment(self, seed = None, bias = 10, scale = 2):
        "create an experiment"
        rndstate   = randstate(seed)
        rnd        = lambda x, *y: rndstate.rand(*y)*(x[1]-x[0])+x[0]
        nbindings  = rndstate.choice(self.nbindings)
        size       = rnd(self.size)
        bins       = self.bins[1]*scale
        maxv       = min(self.bins[0]-bias, int(size/bins))
        pos        = []
        while len(pos) != nbindings:
            pos = np.unique(rndstate.randint(0, maxv, nbindings))
        pos        = np.append(pos, int(size/bins))
        tpl        = deepcopy(self.template.__dict__)
        tpl.pop("bindings")
        tpl.update(positions = np.sort(pos)[::-1]*bins,
                   onrates   = np.insert(rnd(self.onrates,  nbindings), 0, 0),
                   offrates  = np.insert(rnd(self.offrates, nbindings), 0, 0),
                   natures   = ["singlestrand"]+["probe"]*nbindings)
        return self.template.__class__(**tpl)

    def createimage(self, info, bead):
        "transform bead data into an image"
        data  = info['data'][bead]
        bead  = np.vstack([data[i:j] for i, j in info['phases'][:,[5, 6]]])
        bead /= self.bins[1]
        bead -= np.min(bead)-1
        bead  = np.clip(bead, 0., self.bins[0]-1)
        img    = np.zeros((3, self.bins[0], bead.shape[0]), dtype = 'f4')
        zvals  = np.round(bead).astype('i4')
        order  = np.argsort(zvals, axis = 1)
        for i in range(bead.shape[0]):
            bcount = np.bincount(zvals[i,:], minlength = self.bins[0])

            img[0,:,i]     = np.clip(np.log(1+bcount), 0, self.imgclip)

            bcount[zvals[i,-1]] -= 1
            inds           = np.nonzero(bcount)[0]
            valinds        = np.cumsum(np.insert(bcount[inds], 0, 0))
            dzvals         = np.append((bead[i,1:]-bead[i,:-1]), 0)[order[i,:]]
            img[1,inds,i] += [dzvals[valinds[i]:valinds[i+1]].mean()
                              for i in range(len(inds))]

            bcount[zvals[i,-1]] += 1
            bcount[zvals[i,0]]  -= 1
            inds                 = np.nonzero(bcount)[0]
            valinds              = np.cumsum(np.insert(bcount[inds], 0, 0))
            img[2,inds,i]       += [dzvals[valinds[i]:valinds[i+1]].mean()
                                    for i in range(len(inds))]

        return img

    def createtruth(self, experiment: Experiment, info, ibead, bias = 5):
        "transform bead truth into an image"
        truth      = info["truth"][ibead]
        size       = info['phases'][0,6]-info['phases'][0,6]

        img        = np.zeros((self.bins[0], truth.events.shape[0]), dtype = 'f4')
        pos        = bias+np.round(np.array(experiment.positions, dtype = 'f4')
                                   /self.bins[1]).astype('i4')
        for i, j in enumerate(pos):
            img[j,:] = np.log(truth.events[:,i] + 1)

        img[bias]  = size - np.sum(truth.events, axis = 1)
        return img

    def images(self, experiment: Optional[Experiment] = None, nimage = 1, seed = None):
        "create & transform all track data into images"
        cnf  = self.experiment(seed = seed) if experiment is None else experiment
        info = cnf.track(nimage, seed = seed)
        for i in info['data']:
            yield (self.createimage(info, i),
                   self.createtruth(cnf, info, i),
                   cnf.npbindings)
