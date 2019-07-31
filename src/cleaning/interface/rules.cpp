#include <string>
#include "cleaning/interface/aberrant.h"
#include "cleaning/interface/rules.h"
#include "cleaning/interface/rules_doc.h"
#include "cleaning/interface/datacleaning.h"

namespace {
    static std::string alldoc()
    {
        std::string doc =  R"_(Remove specific points, cycles or even the whole
bead depending on a number of criteria implemented in aptly named methods:

PhaseJump
---------
)_";
        doc += PHJUMP_DOC;
        doc += R"_(

Aberrant
--------
)_";
        doc += ABB_DOC;
        doc += R"_(

HFSigma
-------
)_";
        doc += HF_DOC;
        doc += R"_(

Population
----------
)_";
        doc += POP_DOC;
        doc += R"_(

Extent
------
)_";
        doc += EXTENT_DOC;
        doc += R"_(

Pingpong
--------
)_";
        doc += PP_DOC;
        doc += R"_(

Saturation
----------
)_";
        doc += SAT_DOC;
        doc += R"_(

Pseudo-code
-----------

Define:
* Beads(trk) = set of all beads of the track trk
* Cycles(bd) = set of all cycles in bead bd
* Points(cy) = set of all points in cycle cy

For a track trk, cleaning proceeds as follows:
* for bd in Beads(trk):
    * for cy in Cycles(bd):
        * evaluate criteria for cy:
            0. phase jump
    * endfor
    * remove aberrant values
    * for cy in Cycles(bd):
        * evaluate criteria for cy:
            1. population (not aberrant Points(cy)/Points(cy)) > 80%
            2. 0.25 < extent < 2.
            3. hfsigma < 0.0001
            4. hfsigma > 0.01
            5. the series doesn't bounce between 2 values
        * if 0., 1. or 2. or 3. or 4. or 5. are FALSE:
            * remove cy from Cycles(bd)
        * else:
            * keep cy in Cycles(bd)
    * endfor
    * evaluate criteria for bd:
        5. population (Cycles(bd)/initial Cycles(bd)) > 80%
        6. saturation (Cycles(bd)) < 90%
    * if 5. or 6. are FALSE:
        * bd is bad
    * else:
        * bd is good
    * endif
* endfor
)_";
        return doc;
    }
}

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

    void allrule(py::module & mod, py::object & partial)
    {
        std::string doc =  alldoc();

        using CLS = DataCleaning;

        py::class_<CLS> cls(mod, "DataCleaning", doc.c_str());

#       define DPX_ALL_PROP(parent, name)                             \
            cls.def_property(                               \
                 #name,                                               \
                [](CLS const & self) { return self.parent.name; },    \
                [](CLS & self, decltype(CLS().parent.name) const & val) \
                { self.parent.name = val; } \
            );

#       define DPX_ALL_PROP2(parent, name, attr)                      \
            cls.def_property(                               \
                 #name,                                               \
                [](CLS const & self) { return self.parent.attr; },    \
                [](CLS & self, decltype(CLS().parent.attr) const & val) \
                { self.parent.attr = val; } \
            );
        DPX_ALL_PROP(aberrant, constants)
        DPX_ALL_PROP(aberrant, derivative)
        DPX_ALL_PROP(aberrant, localnans)
        DPX_ALL_PROP(aberrant, islands)
        DPX_ALL_PROP(aberrant.derivative, maxabsvalue)
        DPX_ALL_PROP(aberrant.derivative, maxderivate)
        DPX_ALL_PROP(aberrant.constants, mindeltavalue)
        DPX_ALL_PROP2(aberrant.islands, cstmaxderivate, maxderivate)

        cls.def_static(
            "zscaledattributes",
            [] {
               return py::make_tuple(
                    "mindeltavalue", "maxabsvalue", "maxderivate", "cstmaxderivate",
                    "phasejumpheight", "delta",
                    "minhfsigma", "maxhfsigma",
                    "minextent", "maxextent",
                    "mindifference",
                    "maxdisttozero"
            );}
        );

        cls.def(
            "rescale",
            [](CLS const & self, float val)
            {
                auto cpy = self;
                cpy.aberrant.constants.mindeltavalue *= val;
                cpy.aberrant.derivative.maxabsvalue  *= val;
                cpy.aberrant.derivative.maxderivate  *= val;
                cpy.aberrant.islands.maxderivate     *= val;
                cpy.phasejump.phasejumpheight  *= val;
                cpy.phasejump.delta            *= val;
                cpy.hfsigma.minv                     *= val;
                cpy.hfsigma.maxv                     *= val;
                cpy.extent.minv                      *= val;
                cpy.extent.maxv                      *= val;
                cpy.pingpong.mindifference           *= val;
                cpy.saturation.maxdisttozero         *= val;
                return cpy;
            }
        );

        cls.def("aberrant",
            [](CLS const & self, ndarray<float> arr, bool clip)
            { 
                float * data = arr.mutable_data();
                size_t  sz   = arr.size();
                size_t  cnt  = sz;
                {
                    py::gil_scoped_release _;
                    self.aberrant.apply(sz, data, clip);
                    for(size_t i = 0u; i < sz; ++i)
                        if(!std::isfinite(data[i]))
                            --cnt;
                }
                return cnt < size_t(sz*(self.population.minv*1e-2));
            },
            py::arg("beaddata"), py::arg("clip") = false
        );

        DPX_ALL_PROP(phasejump, phasejumpheight)
        DPX_ALL_PROP2(phasejump, maxphasejump, maxv)
        DPX_ALL_PROP(phasejump, delta)
        cls.def("phasejump",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   start,
                          ndarray<int>   stop)
                { 
                    auto x = __applyrule(self.phasejump, _toinput(bead, start, stop));
                    return _totuple(partial, "phasejump", x);
                });
    
        DPX_ALL_PROP2(hfsigma, minhfsigma, minv)
        DPX_ALL_PROP2(hfsigma, maxhfsigma, maxv)
        cls.def("hfsigma",
            [partial](CLS const & self,
                      ndarray<float> bead,
                      ndarray<int>   start,
                      ndarray<int>   stop)
            { 
                auto x = __applyrule(self.hfsigma, _toinput(bead, start, stop));
                return _totuple(partial, "hfsigma", x);
            });

        DPX_ALL_PROP2(population, minpopulation, minv)
        cls.def("population",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   start,
                          ndarray<int>   stop)
                { 
                    auto x = __applyrule(self.population, _toinput(bead, start, stop));
                    return _totuple(partial, "population", x);
                });

        DPX_ALL_PROP2(extent, minextent, minv)
        DPX_ALL_PROP2(extent, maxextent, maxv)
        cls.def("extent",
            [partial](CLS const & self,
                      ndarray<float> bead,
                      ndarray<int>   start,
                      ndarray<int>   stop)
            { 
                auto x = __applyrule(self.extent, _toinput(bead, start, stop));
                return _totuple(partial, "extent", x);
            });

        DPX_ALL_PROP2(pingpong, maxpingpong, maxv)
        DPX_ALL_PROP(pingpong, mindifference)
        cls.def("pingpong",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   start,
                          ndarray<int>   stop)
                { 
                    auto x = __applyrule(self.pingpong, _toinput(bead, start, stop));
                    return _totuple(partial, "pingpong", x);
                });

        DPX_ALL_PROP2(saturation, maxsaturation, maxv)
        DPX_ALL_PROP(saturation, maxdisttozero)
        DPX_ALL_PROP(saturation, satwindow)
        cls.def("saturation",
                [partial](CLS const & self,
                          ndarray<float> bead,
                          ndarray<int>   initstart,
                          ndarray<int>   initstop,
                          ndarray<int>   measstart,
                          ndarray<int>   measstop)
                { 
                    auto x = __applyrule(self.saturation,
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
        allrule      (mod, partial);
    }
}
