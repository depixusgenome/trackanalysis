#include "cleaning/interface/rules.h"

namespace cleaning::datacleaning::rules { namespace {
    static constexpr auto HF_DOC = R"_(Remove cycles with too low or too high a variability.

The variability is measured as the median of the absolute value of the
pointwise derivate of the signal. The median itself is estimated using the
P² quantile estimator algorithm.

Too low a variability is a sign that the tracking algorithm has failed to
compute a new value and resorted to using a previous one.

Too high a variability is likely due to high brownian motion amplified by a
rocking motion of a bead due to the combination of 2 factors:

1. The bead has a prefered magnetisation axis. This creates a prefered
horisontal plane and thus a prefered vertical axis.
2. The hairpin is attached off-center from the vertical axis of the bead.)_";

    static constexpr auto POP_DOC = R"_(Remove cycles with too few good points.

Good points are ones which have not been declared aberrant and which have
a finite value.)_";

    static constexpr auto EXTENT_DOC = R"_(Remove cycles with too great a dynamic range.

The range of Z values is estimated using percentiles robustness purposes. It
is estimated from phases `PHASE.initial` to `PHASE.measure`.)_";

    static constexpr auto PP_DOC = R"_(Remove cycles which play ping-pong.

Some cycles are corrupted by close or passing beads, with the tracker switching
from one bead to another and back. This rules detects such situations by computing
the integral of the absolute value of the derivative of Z, first discarding values
below a givent threshold: those that can be considered due to normal levels of noise.)_";

    static constexpr auto PHJUMP_DOC = R"_(Remove cycles containing phase jumps.

Sometimes the tracking of a fringe may experience a phase-jump of 2π, usually when two fringes 
get too close to each other. This phase-jump will show as a ~1.4µm change of z,
often occuring as a rapid sequence of spikes.
This rule counts the number of such phase-jumps in a given cycle by counting the the number of
values of the absolute discrete derivative in the window (phasejumpheight ± delta).)_";

    static constexpr auto SAT_DOC = R"_(Remove beads which don't have enough cycles ending at zero.

When too many cycles (> 90%) never reach 0 before the end of phase 5, the bead is
discarded. Such a case arises when:

* the hairpin never closes: the force is too high,
* a hairpin structure keeps the hairpin from closing. Such structures should be
detectable in ramp files.
* an oligo is blocking the loop.)_";
}}


namespace cleaning::datacleaning::rules { namespace {
    void hfsigmarule(py::module &mod, py::object &partial)
    {
        auto  doc = HF_DOC;
        using CLS = HFSigmaRule;
        py::class_<CLS> cls(mod, "HFSigmaRule", doc);
        cls.def_readwrite("minhfsigma",  &CLS::minv)
           .def_readwrite("maxhfsigma",  &CLS::maxv)
           .def_static(
                   "zscaledattributes", 
                    []() { return py::make_tuple("minhfsigma", "maxhfsigma"); }
           )
           .def(
                   "rescale", 
                    [](CLS const & self, float val)
                    {
                        auto cpy = self;
                        cpy.minv *= val;
                        cpy.maxv *= val;
                        return cpy;
                    }
           )
           .def("hfsigma",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   start,
                          ndarray<int>   stop)
                { 
                    auto x = __applyrule(self, _toinput(bead, start, stop));
                    return _totuple(partial, "hfsigma", x);
                });
        _defaults(cls);
    }

    void poprule(py::module &mod, py::object &partial)
    {
        auto  doc = POP_DOC;
        using CLS = PopulationRule;
        py::class_<CLS> cls(mod, "PopulationRule", doc);
        cls.def_readwrite("minpopulation",  &CLS::minv)
           .def_static(
                   "zscaledattributes",
                   [] () { return py::make_tuple(); }
           )
           .def(
                   "rescale",
                   [](CLS const & self, float)
                   {
                        auto cpy = self;
                        return cpy;
                   }
           )
           .def("population",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   start,
                          ndarray<int>   stop)
                { 
                    auto x = __applyrule(self, _toinput(bead, start, stop));
                    return _totuple(partial, "population", x);
                });
        _defaults(cls);
    }

    void extentrule(py::module &mod, py::object &partial)
    {
        auto  doc = EXTENT_DOC;
        using CLS = ExtentRule;
        py::class_<CLS> cls(mod, "ExtentRule", doc);
        _pairproperty(cls, "percentiles", &CLS::minpercentile, &CLS::maxpercentile);
        cls.def_readwrite("minextent",  &CLS::minv)
           .def_readwrite("maxextent",  &CLS::maxv)
           .def_static(
                   "zscaledattributes", 
                    []() { return py::make_tuple("minextent", "maxextent"); }
           )
           .def(
                   "rescale", 
                    [](CLS const & self, float val)
                    {
                        auto cpy = self;
                        cpy.minv *= val;
                        cpy.maxv *= val;
                        return cpy;
                    }
           )
           .def("extent",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   start,
                          ndarray<int>   stop)
                { 
                    auto x = __applyrule(self, _toinput(bead, start, stop));
                    return _totuple(partial, "extent", x);
                });
        _defaults(cls);
    }

    void pingpongrule(py::module &mod, py::object &partial)
    {
        auto  doc = PP_DOC;
        using CLS = PingPongRule;
        py::class_<CLS> cls(mod, "PingPongRule", doc);
        _pairproperty(cls, "percentiles",   &CLS::minpercentile, &CLS::maxpercentile);
        cls.def_readwrite("maxpingpong",    &CLS::maxv)
           .def_readwrite("mindifference",  &CLS::mindifference)
           .def_static(
                   "zscaledattributes",
                    [] () { return py::make_tuple("mindifference"); }
           )
           .def(
                   "rescale",
                   [](CLS const & self, float val)
                   {
                        auto cpy = self;
                        cpy.mindifference *= val;
                        return cpy;
                   }
           )
           .def("pingpong",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   start,
                          ndarray<int>   stop)
                { 
                    auto x = __applyrule(self, _toinput(bead, start, stop));
                    return _totuple(partial, "pingpong", x);
                });
        _defaults(cls);
    }

    void phasejumprule(py::module &mod, py::object & partial)
    {
        auto  doc = PHJUMP_DOC;
        using CLS = PhaseJumpRule;
        py::class_<CLS> cls(mod, "PhaseJumpRule", doc);
        cls.def_readwrite("phasejumpheight",  &CLS::phasejumpheight)
           .def_readwrite("maxphasejump",     &CLS::maxv)
           .def_readwrite("delta",            &CLS::delta)
           .def_static(
                   "zscaledattributes",
                    [] () { return py::make_tuple("phasejumpheight", "delta"); }
           )
           .def(
                   "rescale",
                   [](CLS const & self, float val)
                   {
                        auto cpy = self;
                        cpy.phasejumpheight *= val;
                        cpy.delta *= val;
                        return cpy;
                   }
           )
           .def("phasejump",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   start,
                          ndarray<int>   stop)
                { 
                    auto x = __applyrule(self, _toinput(bead, start, stop));
                    return _totuple(partial, "phasejump", x);
                });
        _defaults(cls);
    }

    void satrule(py::module & mod, py::object & partial)
    {
        auto  doc = SAT_DOC;
        using CLS = SaturationRule;
        py::class_<CLS> cls(mod, "SaturationRule", doc);
        cls.def_readwrite("maxsaturation",  &CLS::maxv)
           .def_readwrite("maxdisttozero",  &CLS::maxdisttozero)
           .def_readwrite("satwindow",      &CLS::satwindow)
           .def_static(
                   "zscaledattributes",
                   [] () { return py::make_tuple("maxdisttozero"); }
           )
           .def(
                   "rescale",
                   [](CLS const & self, float val)
                   {
                        auto cpy = self;
                        cpy.maxdisttozero *= val;
                        return cpy;
                   }
           )
           .def("saturation",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   initstart,
                          ndarray<int>   initstop,
                          ndarray<int>   measstart,
                          ndarray<int>   measstop)
                { 
                    auto x = __applyrule(self,
                                         _toinput(bead, initstart, initstop),
                                         _toinput(bead, measstart, measstop));
                    return _totuple(partial, "saturation", x);
                });
        _defaults(cls);
    }
}}

namespace cleaning::datacleaning::rules {
    void pymodule(py::module & mod)
    {
        auto partial = dpx::pyinterface::make_namedtuple(mod, "Partial",
                "name",    "",
                "min",     ndarray<float>(0),
                "max",     ndarray<float>(0),
                "values",  ndarray<float>(0));

        hfsigmarule  (mod, partial);
        poprule      (mod, partial);
        extentrule   (mod, partial);
        pingpongrule (mod, partial);
        phasejumprule(mod, partial);
        satrule      (mod, partial);
    }
}
