#include <cmath>
#include <type_traits>
#include <typeinfo>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "cleaning/datacleaning.h"

namespace cleaning { // generic meta functions
    template <typename T>
    using ndarray = pybind11::array_t<T, pybind11::array::c_style>;

    template <typename T>
    inline void _get(std::false_type, T & inst, char const * name, pybind11::dict & kwa)
    {
        if(kwa.contains(name))
            inst = kwa[name].cast<T>();
    }

    template <typename T>
    inline void _get(std::false_type, T & val1, T & val2, char const * name, pybind11::dict & kwa)
    {
        if(kwa.contains(name))
        {
            val1 = kwa[name][pybind11::int_(0)].cast<T>();
            val2 = kwa[name][pybind11::int_(1)].cast<T>();
        }
    }

    template <typename T>
    inline void _get(std::true_type, T const & inst, char const * name, pybind11::dict & kwa)
    { kwa[name] = inst; }

    template <typename T>
    inline void _get(std::true_type, T const & val1, T const & val2, char const * name, pybind11::dict & kwa)
    { kwa[name] = pybind11::make_tuple(val1, val2); }

    void _has(...) {}


    template <typename T, typename K1, typename K2>
    void _pairproperty(pybind11::class_<T> & cls, char const * name,
                       K1 T::*first, K2  T::*second)
    {
       cls.def_property(name,
                        [&](T const & self) 
                        { return pybind11::make_tuple(self.*first, self.*second); },
                        [&](T & self, pybind11::object vals) 
                        {
                          if(vals.is_none()) {
                              self.*first  = 0.0f;
                              self.*second = 100.0f;
                          } else {
                              self.*first  = vals[pybind11::int_(0)].cast<float>();
                              self.*second = vals[pybind11::int_(1)].cast<float>();
                          }
                        });
    }

    template <typename T, typename K>
    using issame = std::enable_if<
                           std::is_same<T, K>::value
                        || std::is_same<T, K const>::value>;
}

namespace cleaning { // fromkwa specializations
    template <typename T>
    typename issame<T, SaturationRule>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _get(std::is_const<T>(), inst.maxv,          "maxsaturation", kwa);
        _get(std::is_const<T>(), inst.maxdisttozero, "maxdisttozero", kwa);
        _get(std::is_const<T>(), inst.satwindow,     "satwindow",     kwa);
    };

    template <typename T>
    typename issame<T, PingPongRule>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _get(std::is_const<T>(), inst.maxv,          "maxpingpong",   kwa);
        _get(std::is_const<T>(), inst.mindifference, "mindifference", kwa);
        _get(std::is_const<T>(), inst.minpercentile, inst.maxpercentile, "percentiles", kwa);
    }

    template <typename T>
    typename issame<T, PopulationRule>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    { _get(std::is_const<T>(), inst.minv,    "minhfsigma",  kwa); }

    template <typename T>
    typename issame<T, HFSigmaRule>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _get(std::is_const<T>(), inst.minv,    "minhfsigma",  kwa);
        _get(std::is_const<T>(), inst.maxv,    "maxhfsigma",  kwa);
    }

    template <typename T>
    typename issame<T, ExtentRule>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _get(std::is_const<T>(), inst.minv,    "minextent",  kwa);
        _get(std::is_const<T>(), inst.maxv,    "maxextent",  kwa);
        _get(std::is_const<T>(), inst.minpercentile, inst.maxpercentile, "percentiles", kwa);
    }

    template <typename T>
    typename issame<T, DerivateSuppressor<float>>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _get(std::is_const<T>(), inst.maxderivate, "maxderivate", kwa);
        _get(std::is_const<T>(), inst.maxabsvalue, "maxabsvalue", kwa);
    }

    template <typename T>
    typename issame<T, ConstantValuesSuppressor<float>>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _get(std::is_const<T>(), inst.mindeltarange, "mindeltarange", kwa);
        _get(std::is_const<T>(), inst.mindeltavalue, "mindeltavalue", kwa);
    }

    template <typename T>
    typename issame<T, NaNDerivateIslands>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _get(std::is_const<T>(), inst.riverwidth,  "riverwidth",  kwa);
        _get(std::is_const<T>(), inst.islandwidth, "islandwidth", kwa);
        _get(std::is_const<T>(), inst.ratio,       "ratio",       kwa);
        _get(std::is_const<T>(), inst.maxderivate, "maxderivate", kwa);
    }

    template <typename T>
    typename issame<T, LocalNaNPopulation>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _get(std::is_const<T>(), inst.window, "window", kwa);
        _get(std::is_const<T>(), inst.ratio,  "ratio",  kwa);
    }

    template <typename T>
    typename issame<T, AberrantValuesRule>::type
    _fromkwa(T & inst, pybind11::dict & kwa)
    {
        _fromkwa(inst.constants,  kwa);
        _fromkwa(inst.derivative, kwa);
        if(!std::is_const<T>::value)
        {
            _get(std::is_const<T>(), inst.islands,   "islands",   kwa);
            _get(std::is_const<T>(), inst.localnans, "localnans", kwa);
        }

        _get(std::is_const<T>(), inst.islands.riverwidth,  "cstriverwidth",  kwa);
        _get(std::is_const<T>(), inst.islands.islandwidth, "cstislandwidth", kwa);
        _get(std::is_const<T>(), inst.islands.ratio,       "cstratio",       kwa);
        _get(std::is_const<T>(), inst.islands.maxderivate, "cstmaxderivate", kwa);
        _get(std::is_const<T>(), inst.localnans.window, "nanwindow", kwa);
        _get(std::is_const<T>(), inst.localnans.ratio,  "nanratio",  kwa);
    }

    template <typename T>
    std::unique_ptr<T>
    _toptr(pybind11::dict kwa)
    {
        std::unique_ptr<T> ptr(new T());
        _fromkwa<T>(*ptr, kwa);
        return ptr;
    }


    template <typename T>
    pybind11::dict _getkwa(T const & inst) 
    { 
        pybind11::dict d;
        _fromkwa<T const>(inst, d);
        return d; 
    }

    template <typename T>
    void constant(pybind11::object self, ndarray<T> & pydata)
    {
        if(pybind11::hasattr(self, "constants"))
            self = self.attr("constants");

        auto a = self.attr("mindeltarange").cast<size_t>();
        auto b = self.attr("mindeltavalue").cast<T>();
        ConstantValuesSuppressor<T> itm({b, a});
        itm.apply(pydata.size(), pydata.mutable_data());
    }

    template <typename T>
    void clip(pybind11::object self, bool doclip, float azero, ndarray<T> & pydata)
    {
        if(pybind11::hasattr(self, "derivative"))
            self = self.attr("constants");
        auto a = self.attr("maxabsvalue").cast<T>();
        auto b = self.attr("maxderivate").cast<T>();
        DerivateSuppressor<T> itm({a, b});
        itm.apply(pydata.size(), pydata.mutable_data(), doclip, azero);
    }
}

namespace cleaning { // the module
    template <typename T>
    void _defaults(pybind11::class_<T> & cls)
    {
        cls.def(pybind11::init([](pybind11::kwargs kwa) { return _toptr<T>(kwa); }))
           .def("configure", [](T & i, pybind11::dict d){ _fromkwa<T>(i, d); })
           .def("__eq__", 
                [](pybind11::object & a, pybind11::object b) -> bool
                { 
                    if(!a.attr("__class__").is(b.attr("__class__")))
                        return false;
                    return std::memcmp(a.cast<T*>(), b.cast<T*>(), sizeof(T)) == 0;
                })
           .def(pybind11::pickle(&_getkwa<T>, &_toptr<T>));
    }

    pybind11::tuple _totuple(pybind11::object cls, const char * name, DataOutput const & out)
    {
        auto cnv = [](auto x) { return ndarray<typename decltype(x)::value_type>(x.size(), x.data()); };
        auto x1  = cnv(out.minv), x2 = cnv(out.maxv); auto x3 = cnv(out.values);
        return cls(name, x1, x2, x3);
    }

    DataInfo _toinput(ndarray<float> bead, ndarray<long long> phase1, ndarray<long long> phase2)
    { return { size_t(bead.size()), bead.data(),
               size_t(phase1.size()), phase1.data(), phase2.data() }; }

    template <typename T, typename ...K>
    DataOutput __applyrule(T const & self, K && ... info)
    {
        pybind11::gil_scoped_release _;
        return self.apply(info...);
    }

    void pymodule(pybind11::module & mod)
    {
        using namespace pybind11::literals;

        {
            using CLS = ConstantValuesSuppressor<float>;
            auto doc = R"_(Removes constant values.
* |z[I-mindeltarange+1] - z[I-mindeltarange+2] | < mindeltavalue
*  & ...
*  & |z[I-mindeltarange+1] - z[I]|              < mindeltavalue
*  & n ∈ [I-mindeltarange+2, I])_";

            mod.def("constant", constant<float>,  "datacleaningobject"_a, "array"_a);
            mod.def("constant", constant<double>,  "datacleaningobject"_a, "array"_a, doc);

            pybind11::class_<CLS> cls(mod, "ConstantValuesSuppressor", doc);
            cls.def_readwrite("mindeltarange", &CLS::mindeltarange)
               .def_readwrite("mindeltavalue", &CLS::mindeltavalue)
               .def("apply",
                    [](CLS const & self, ndarray<float> & arr)
                    { self.apply(arr.size(), arr.mutable_data()); });
            _defaults(cls);
        }

        {

            auto doc = R"_(Removes aberrant values

A value at position *n* is aberrant if either or both:
* |z[n] - median(z)| > maxabsvalue
* |(z[n+1]-z[n-1])/2-z[n]| > maxderivate

Aberrant values are replaced by:
* *NaN* if *clip* is true,
* *maxabsvalue ± median*, whichever is closest, if *clip* is false.

returns: *True* if the number of remaining values is too low)_";

            mod.def("clip", clip<float>,
                    "datacleaningobject"_a, "clip"_a, "zero"_a, "array"_a);
            mod.def("clip", clip<double>,
                    "datacleaningobject"_a, "clip"_a, "zero"_a, "array"_a, doc);

            using CLS = DerivateSuppressor<float>;
            pybind11::class_<CLS> cls(mod, "DerivateSuppressor", doc);
            cls.def_readwrite("maxderivate", &CLS::maxderivate)
               .def_readwrite("maxabsvalue", &CLS::maxabsvalue)
               .def("apply",
                    [](CLS const & self, ndarray<float> & arr, bool clip, float zero)
                    { self.apply(arr.size(), arr.mutable_data(), clip, zero); });
            _defaults(cls);
        }

        {
            using CLS = LocalNaNPopulation;
            auto doc = R"_(Removes frames which have NaN values to their right and their left)_";
            pybind11::class_<CLS> cls(mod, "LocalNaNPopulation", doc);
            cls.def_readwrite("window", &CLS::window)
               .def_readwrite("ratio",  &CLS::ratio)
               .def("apply",
                    [](CLS const & self, ndarray<float> & arr)
                    { self.apply(arr.size(), arr.mutable_data()); });
            _defaults(cls);
        }

        {
            auto doc = R"_(Removes frame intervals with the following characteristics:
* there are *islandwidth* or less good values in a row,
* with a derivate of at least *maxderivate*
* surrounded by *riverwidth* or more NaN values in a row on both sides)_";

            using CLS = NaNDerivateIslands;
            pybind11::class_<CLS> cls(mod, "NaNDerivateIslands", doc);
            cls.def_readwrite("riverwidth",  &CLS::riverwidth)
               .def_readwrite("islandwidth", &CLS::islandwidth)
               .def_readwrite("ratio",       &CLS::ratio)
               .def_readwrite("maxderivate", &CLS::maxderivate)
               .def("apply", [](CLS const & self, ndarray<float> & arr)
                    { self.apply(arr.size(), arr.mutable_data()); });
            _defaults(cls);
        }

        {
            auto doc = R"_(Removes aberrant values.
A value at position *n* is aberrant if any:

* |z[n] - median(z)| > maxabsvalue
* |(z[n+1]-z[n-1])/2-z[n]| > maxderivate
* |z[I-mindeltarange+1] - z[I-mindeltarange+2] | < mindeltavalue
  && ...
  && |z[I-mindeltarange+1] - z[I]|               < mindeltavalue
  && n ∈ [I-mindeltarange+2, I]
* #{z[I-nanwindow//2:I+nanwindow//2] is nan} < nanratio*nanwindow)_";
            using CLS = AberrantValuesRule;
            pybind11::class_<CLS> cls(mod, "AberrantValuesRule", doc);
            cls.def_readwrite("constants",  &CLS::constants)
               .def_readwrite("derivative", &CLS::derivative)
               .def_readwrite("localnans",  &CLS::localnans)
               .def_readwrite("islands",    &CLS::islands)
               .def("aberrant",
                    [](CLS const & self, ndarray<float> & arr, bool clip)
                    { self.apply(arr.size(), arr.mutable_data(), clip); },
                    pybind11::arg("beaddata"), pybind11::arg("clip") = true);
            _defaults(cls);
        }

        pybind11::list lst;
        lst.append(pybind11::make_tuple("name",   pybind11::str("").attr("__class__")));
        lst.append(pybind11::make_tuple("min",    ndarray<float>(0).attr("__class__")));
        lst.append(pybind11::make_tuple("max",    ndarray<float>(0).attr("__class__")));
        lst.append(pybind11::make_tuple("values", ndarray<float>(0).attr("__class__")));
        auto partial(pybind11::module::import("typing").attr("NamedTuple")("Partial", lst));
        setattr(mod, "Partial", partial);

        {
            auto doc = R"_(Remove cycles with too low or too high a variability.

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

            using CLS = HFSigmaRule;
            pybind11::class_<CLS> cls(mod, "HFSigmaRule", doc);
            cls.def_readwrite("minhfsigma",  &CLS::minv)
               .def_readwrite("maxhfsigma",  &CLS::maxv)
               .def("hfsigma",
                    [partial](CLS const & self,
                              ndarray<float> bead,
                              ndarray<long long>   start,
                              ndarray<long long>   stop)
                    { 
                        auto x = __applyrule(self, _toinput(bead, start, stop));
                        return _totuple(partial, "hfsigma", x);
                    });
            _defaults(cls);
        }

        {
            auto doc = R"_(Remove cycles with too few good points.

Good points are ones which have not been declared aberrant and which have
a finite value.)_";

            using CLS = PopulationRule;
            pybind11::class_<CLS> cls(mod, "PopulationRule", doc);
            cls.def_readwrite("minpopulation",  &CLS::minv)
               .def("population",
                    [partial](CLS const & self,
                              ndarray<float> bead,
                              ndarray<long long>   start,
                              ndarray<long long>   stop)
                    { 
                        auto x = __applyrule(self, _toinput(bead, start, stop));
                        return _totuple(partial, "population", x);
                    });
            _defaults(cls);
        }

        {
            auto doc = R"_(Remove cycles with too great a dynamic range.

The range of Z values is estimated using percentiles robustness purposes. It
is estimated from phases `PHASE.initial` to `PHASE.measure`.)_";

            using CLS = ExtentRule;
            pybind11::class_<CLS> cls(mod, "ExtentRule", doc);
            _pairproperty(cls, "percentiles", &CLS::minpercentile, &CLS::maxpercentile);
            cls.def_readwrite("minextent",  &CLS::minv)
               .def_readwrite("maxextent",  &CLS::maxv)
               .def("extent",
                    [partial](CLS const & self,
                              ndarray<float> bead,
                              ndarray<long long>   start,
                              ndarray<long long>   stop)
                    { 
                        auto x = __applyrule(self, _toinput(bead, start, stop));
                        return _totuple(partial, "extent", x);
                    });
            _defaults(cls);
        }

        {
            auto doc = R"_(Remove cycles which play ping-pong.
            
Some cycles are corrupted by close or passing beads, with the tracker switching
from one bead to another and back. This rules detects such situations by computing
the integral of the absolute value of the derivative of Z, first discarding values
below a givent threshold: those that can be considered due to normal levels of noise.)_";

            using CLS = PingPongRule;
            pybind11::class_<CLS> cls(mod, "PingPongRule", doc);
            _pairproperty(cls, "percentiles",   &CLS::minpercentile, &CLS::maxpercentile);
            cls.def_readwrite("maxpingpong",    &CLS::maxv)
               .def_readwrite("mindifference",  &CLS::mindifference)
               .def("pingpong",
                    [partial](CLS const & self,
                              ndarray<float> bead,
                              ndarray<long long>   start,
                              ndarray<long long>   stop)
                    { 
                        auto x = __applyrule(self, _toinput(bead, start, stop));
                        return _totuple(partial, "pingpong", x);
                    });
            _defaults(cls);
        }
        {
            auto doc = R"_(Remove beads which don't have enough cycles ending at zero.

When too many cycles (> 90%) never reach 0 before the end of phase 5, the bead is
discarded. Such a case arises when:

* the hairpin never closes: the force is too high,
* a hairpin structure keeps the hairpin from closing. Such structures should be
detectable in ramp files.
* an oligo is blocking the loop.)_";

            using CLS = SaturationRule;
            pybind11::class_<CLS> cls(mod, "SaturationRule", doc);
            cls.def_readwrite("maxsaturation",  &CLS::maxv)
               .def_readwrite("maxdisttozero",  &CLS::maxdisttozero)
               .def_readwrite("satwindow",      &CLS::satwindow)
               .def("saturation",
                    [partial](CLS const & self,
                              ndarray<float> bead,
                              ndarray<long long>   initstart,
                              ndarray<long long>   initstop,
                              ndarray<long long>   measstart,
                              ndarray<long long>   measstop)
                    { 
                        auto x = __applyrule(self,
                                             _toinput(bead, initstart, initstop),
                                             _toinput(bead, measstart, measstop));
                        return _totuple(partial, "saturation", x);
                    });
            _defaults(cls);
        }
    }
}
