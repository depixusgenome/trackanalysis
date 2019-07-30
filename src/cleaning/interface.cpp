#include <cmath>
#include <type_traits>
#include <typeinfo>
#include "utils/pybind11.hpp"
#include "cleaning/datacleaning.h"
#include "cleaning/beadsubtraction.h"

namespace py = pybind11;
using dpx::pyinterface::ndarray;
using dpx::pyinterface::toarray;

namespace cleaning { // generic meta functions
    template <typename T>
    inline void _get(std::false_type, T & inst, char const * name, py::dict & kwa)
    {
        if(kwa.contains(name))
            inst = kwa[name].cast<T>();
    }

    template <typename T>
    inline void _get(std::false_type, T & val1, T & val2, char const * name, py::dict & kwa)
    {
        if(kwa.contains(name))
        {
            val1 = kwa[name][py::int_(0)].cast<T>();
            val2 = kwa[name][py::int_(1)].cast<T>();
        }
    }

    template <typename T>
    inline void _get(std::true_type, T const & inst, char const * name, py::dict & kwa)
    { kwa[name] = inst; }

    template <typename T>
    inline void _get(std::true_type, T const & val1, T const & val2, char const * name, py::dict & kwa)
    { kwa[name] = py::make_tuple(val1, val2); }

    void _has(...) {}


    template <typename T, typename K1, typename K2>
    void _pairproperty(py::class_<T> & cls, char const * name,
                       K1 T::*first, K2  T::*second)
    {
       cls.def_property(name,
                        [&](T const & self) 
                        { return py::make_tuple(self.*first, self.*second); },
                        [&](T & self, py::object vals) 
                        {
                          if(vals.is_none()) {
                              self.*first  = 0.0f;
                              self.*second = 100.0f;
                          } else {
                              self.*first  = vals[py::int_(0)].cast<float>();
                              self.*second = vals[py::int_(1)].cast<float>();
                          }
                        });
    }

    template <typename T, typename K>
    using issame = std::enable_if<
                           std::is_same<T, K>::value
                        || std::is_same<T, K const>::value>;
}

namespace cleaning { namespace beadsubtraction {
#   define DPX_INIT_RED                                                         \
        if(pydata.size() == 0)                                                  \
            return ndarray<float>(0);                                           \
                                                                                \
        if(pydata.size() == 1)                                                  \
            return toarray(pydata[0]);                                          \
                                                                                \
        std::vector<data_t> data;                                               \
        for(auto const & i: pydata)                                             \
            data.emplace_back(i.data(), i.size());                              \
                                                                                \
        size_t total = 0u;                                                      \
        for(auto const & i: data)                                               \
            total = std::max(total, std::get<1>(i));

    ndarray<float> reducesignal(std::string tpe, size_t i1, size_t i2,
                                std::vector<ndarray<float>> pydata)
    {
        DPX_INIT_RED
        return toarray(total,
                       [&]()
                       {
                           return (tpe == "median" ? mediansignal(data, i1, i2) :
                                   tpe == "stddev" ? stddevsignal(data, i1, i2) :
                                   meansignal(data, i1, i2));
                       });
    }

    ndarray<float> reducesignal2(std::string tpe,
                                 std::vector<ndarray<float>> pydata)
    { return reducesignal(tpe, 0, 0, pydata); }

    ndarray<float> reducesignal3(std::string tpe,
                                 std::vector<ndarray<float>> pydata,
                                 std::vector<ndarray<int>>   pyphase)
    {
        int const * phases[] = {pyphase[0].data(),
                                pyphase[1].data(),
                                pyphase[2].data()};
        size_t      sz       =  pyphase[0].size();

        DPX_INIT_RED
        auto pyout = toarray(total, std::numeric_limits<float>::quiet_NaN());
        auto ptr   = pyout.mutable_data();
        {
            py::gil_scoped_release _;
            for(size_t i = 0; i < sz; ++i)
            {
                auto i1(phases[0][i]);
                auto i2(phases[1][i]-i1), i3(phases[2][i]-i1);
                auto i4(i+1 < sz ? phases[0][i+1] : total);

                std::vector<data_t> tmp;
                for(auto const & i: data)
                    tmp.emplace_back(std::get<0>(i)+i1, std::min(i4,std::get<1>(i))-i1);

                auto out(tpe == "median" ? mediansignal(tmp, i2, i3) :
                         tpe == "stddev" ? stddevsignal(tmp, i2, i3) :
                         meansignal(tmp, i2, i3));
                std::copy(out.begin(), out.end(), ptr+i1);
            }
        }
        return pyout;
    }

    ndarray<float> pyphasebaseline1(std::string tpe,
                                  ndarray<float> pydata,
                                  ndarray<int>   pyi1,
                                  ndarray<int>   pyi2)
    {
        int const * i1 = pyi1.data();
        int const * i2 = pyi2.data();
        size_t      sz = pyi1.size();

        ndarray<float> pyout(sz);
        auto ptr(pyout.mutable_data());
        std::fill(ptr, ptr+sz, std::numeric_limits<float>::quiet_NaN());

        if(sz == 0)
            return pyout;

        data_t data = {pydata.data(), pydata.size()};
        {
            py::gil_scoped_release _;
            auto out = phasebaseline(tpe, data, sz, i1, i2);
            std::copy(out.begin(), out.end(), ptr);
        }
        return pyout;
    }

    ndarray<float> pyphasebaseline(std::string tpe,
                                 std::vector<ndarray<float>> pydata,
                                 ndarray<int>                pyi1,
                                 ndarray<int>                pyi2)
    {
        int const * i1 = pyi1.data();
        int const * i2 = pyi2.data();
        size_t      sz = pyi1.size();

        if(pydata.size() == 0 || sz == 0)
            return toarray(sz, std::numeric_limits<float>::quiet_NaN());

        std::vector<data_t> data;
        for(auto const & i: pydata)
            data.emplace_back(i.data(), i.size());
        return toarray(sz, [&]() { return phasebaseline(tpe, data, sz, i1, i2); });
    }

    ndarray<int>  pydzcount(float threshold,
                            ndarray<float> pydata,
                            ndarray<int>   pyi1,
                            ndarray<int>   pyi2)
    {
#       define PY_DZCOUNT_INPT(CODE)                \
        int const    * i1   = pyi1.data();          \
        int const    * i2   = pyi2.data();          \
        size_t         sz   = pyi1.size();          \
        float const  * data = pydata.data();        \
        if(pydata.size() == 0 || pyi1.size() == 0)  \
            return CODE;

        PY_DZCOUNT_INPT(toarray(sz, 0))
        return toarray(sz, [&]() { return dzcount(threshold, sz, data, i1, i2); });
    }

    size_t  pydzcount2(float dzthr,
                       ndarray<float> pydata,
                       ndarray<int>   pyi1,
                       ndarray<int>   pyi2)
    {
        PY_DZCOUNT_INPT(0u)
        return dztotalcount(dzthr, sz, data, i1, i2);
    }

    void pymodule(py::module & mod)
    {
        using namespace py::literals;
        mod.def("reducesignals", reducesignal);
        mod.def("reducesignals", reducesignal2);
        mod.def("reducesignals", reducesignal3);
        mod.def("phasebaseline", pyphasebaseline);
        mod.def("phasebaseline", pyphasebaseline1);

        auto doc = R"_(Return an array with the number of frames with to low a derivative.)_";
        mod.def("dzcount", pydzcount,  doc);
        doc = R"_(Return the number of frames with to low a derivative.)_";
        mod.def("dztotalcount", pydzcount2, doc);
    }
}}

namespace cleaning { namespace datacleaning {
    namespace { // fromkwa specializations
        template <typename T>
        typename issame<T, SaturationRule>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.maxv,          "maxsaturation", kwa);
            _get(std::is_const<T>(), inst.maxdisttozero, "maxdisttozero", kwa);
            _get(std::is_const<T>(), inst.satwindow,     "satwindow",     kwa);
        };

        template <typename T>
        typename issame<T, PingPongRule>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.maxv,          "maxpingpong",   kwa);
            _get(std::is_const<T>(), inst.mindifference, "mindifference", kwa);
            _get(std::is_const<T>(), inst.minpercentile, inst.maxpercentile, "percentiles", kwa);
        }

        template <typename T>
        typename issame<T, PhaseJumpRule>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.maxv,             "maxphasejump",     kwa);
            _get(std::is_const<T>(), inst.phasejumpheight,  "phasejumpheight",  kwa);
            _get(std::is_const<T>(), inst.delta,            "delta",            kwa);
        }

        template <typename T>
        typename issame<T, PopulationRule>::type
        _fromkwa(T & inst, py::dict & kwa)
        { _get(std::is_const<T>(), inst.minv,    "minpopulation",  kwa); }

        template <typename T>
        typename issame<T, HFSigmaRule>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.minv,    "minhfsigma",  kwa);
            _get(std::is_const<T>(), inst.maxv,    "maxhfsigma",  kwa);
        }

        template <typename T>
        typename issame<T, ExtentRule>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.minv,    "minextent",  kwa);
            _get(std::is_const<T>(), inst.maxv,    "maxextent",  kwa);
            _get(std::is_const<T>(), inst.minpercentile, inst.maxpercentile, "percentiles", kwa);
        }

        template <typename T>
        typename issame<T, DerivateSuppressor<float>>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.maxderivate, "maxderivate", kwa);
            _get(std::is_const<T>(), inst.maxabsvalue, "maxabsvalue", kwa);
        }

        template <typename T>
        typename issame<T, ConstantValuesSuppressor<float>>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.mindeltarange, "mindeltarange", kwa);
            _get(std::is_const<T>(), inst.mindeltavalue, "mindeltavalue", kwa);
        }

        template <typename T>
        typename issame<T, NaNDerivateIslands>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.riverwidth,  "riverwidth",  kwa);
            _get(std::is_const<T>(), inst.islandwidth, "islandwidth", kwa);
            _get(std::is_const<T>(), inst.ratio,       "ratio",       kwa);
            _get(std::is_const<T>(), inst.maxderivate, "maxderivate", kwa);
        }

        template <typename T>
        typename issame<T, LocalNaNPopulation>::type
        _fromkwa(T & inst, py::dict & kwa)
        {
            _get(std::is_const<T>(), inst.window, "window", kwa);
            _get(std::is_const<T>(), inst.ratio,  "ratio",  kwa);
        }

        template <typename T>
        typename issame<T, AberrantValuesRule>::type
        _fromkwa(T & inst, py::dict & kwa)
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
        _toptr(py::dict kwa)
        {
            std::unique_ptr<T> ptr(new T());
            _fromkwa<T>(*ptr, kwa);
            return ptr;
        }


        template <typename T>
        py::dict _getkwa(T const & inst) 
        { 
            py::dict d;
            _fromkwa<T const>(inst, d);
            return d; 
        }

        template <typename T>
        void constant(py::object self, ndarray<T> pydata)
        {
            if(py::hasattr(self, "constants"))
                self = self.attr("constants");

            auto a = self.attr("mindeltarange").cast<size_t>();
            auto b = self.attr("mindeltavalue").cast<T>();
            ConstantValuesSuppressor<T> itm; itm.mindeltavalue = b; itm.mindeltarange = a;
            itm.apply(pydata.size(), pydata.mutable_data());
        }

        template <typename T>
        void clip(py::object self, bool doclip, float azero, ndarray<T> pydata)
        {
            if(py::hasattr(self, "derivative"))
                self = self.attr("constants");
            auto a = self.attr("maxabsvalue").cast<T>();
            auto b = self.attr("maxderivate").cast<T>();
            DerivateSuppressor<T> itm; itm.maxabsvalue = a; itm.maxderivate = b;
            itm.apply(pydata.size(), pydata.mutable_data(), doclip, azero);
        }
    }

    template <typename T>
    void _defaults(py::class_<T> & cls)
    {
        cls.def(py::init([](py::kwargs kwa) { return _toptr<T>(kwa); }))
           .def("configure", [](T & i, py::dict d){ _fromkwa<T>(i, d); })
           .def("__eq__",
                [](py::object & a, py::object b) -> bool
                { 
                    if(!a.attr("__class__").is(b.attr("__class__")))
                        return false;
                    return std::memcmp(a.cast<T*>(), b.cast<T*>(), sizeof(T)) == 0;
                })
           .def(py::pickle(&_getkwa<T>, &_toptr<T>));
    }

    py::tuple _totuple(py::object cls, const char * name, DataOutput const & out)
    {
        auto cnv = [](auto x) { return ndarray<typename decltype(x)::value_type>(x.size(), x.data()); };
        auto x1  = cnv(out.minv), x2 = cnv(out.maxv); auto x3 = cnv(out.values);
        return cls(name, x1, x2, x3);
    }

    DataInfo _toinput(ndarray<float> bead, ndarray<int> phase1, ndarray<int> phase2)
    { return { size_t(bead.size()), bead.data(),
               size_t(phase1.size()), phase1.data(), phase2.data() }; }

    template <typename T, typename ...K>
    DataOutput __applyrule(T const & self, K && ... info)
    {
        py::gil_scoped_release _;
        return self.apply(info...);
    }

    void pymodule(py::module & mod)
    {
        using namespace py::literals;

        {
            using CLS = ConstantValuesSuppressor<float>;
            auto doc = R"_(Removes constant values.
* |z[I-mindeltarange+1] - z[I-mindeltarange+2] | < mindeltavalue
*  & ...
*  & |z[I-mindeltarange+1] - z[I]|              < mindeltavalue
*  & n ∈ [I-mindeltarange+2, I])_";

            mod.def("constant", constant<float>,  "datacleaningobject"_a, "array"_a);
            mod.def("constant", constant<double>,  "datacleaningobject"_a, "array"_a, doc);

            py::class_<CLS> cls(mod, "ConstantValuesSuppressor", doc);
            cls.def_readwrite("mindeltarange", &CLS::mindeltarange)
               .def_readwrite("mindeltavalue", &CLS::mindeltavalue)
               .def_static(
                       "zscaledattributes", 
                        []() { return py::make_tuple("mindeltavalue"); }
               )
               .def(
                       "rescale", 
                        [](CLS const & self, float val)
                        {
                            auto cpy           = self;
                            cpy.mindeltavalue *= val;
                            return cpy;
                        }
               )
               .def("apply",
                    [](CLS const & self, ndarray<float> arr)
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
            py::class_<CLS> cls(mod, "DerivateSuppressor", doc);
            cls.def_readwrite("maxderivate", &CLS::maxderivate)
               .def_readwrite("maxabsvalue", &CLS::maxabsvalue)
               .def_static(
                       "zscaledattributes", 
                        []() { return py::make_tuple("maxabsvalue", "maxderivate"); }
               )
               .def(
                       "rescale", 
                        [](CLS const & self, float val)
                        {
                            auto cpy = self;
                            cpy.maxabsvalue *= val;
                            cpy.maxderivate *= val;
                            return cpy;
                        }
               )
               .def("apply",
                    [](CLS const & self, ndarray<float> arr, bool clip, float zero)
                    { self.apply(arr.size(), arr.mutable_data(), clip, zero); });
            _defaults(cls);
        }

        {
            using CLS = LocalNaNPopulation;
            auto doc = R"_(Removes frames which have NaN values to their right and their left)_";
            py::class_<CLS> cls(mod, "LocalNaNPopulation", doc);
            cls.def_readwrite("window", &CLS::window)
               .def_readwrite("ratio",  &CLS::ratio)
               .def("apply",
                    [](CLS const & self, ndarray<float> arr)
                    { self.apply(arr.size(), arr.mutable_data()); });
            _defaults(cls);
        }

        {
            auto doc = R"_(Removes frame intervals with the following characteristics:
* there are *islandwidth* or less good values in a row,
* with a derivate of at least *maxderivate*
* surrounded by *riverwidth* or more NaN values in a row on both sides)_";

            using CLS = NaNDerivateIslands;
            py::class_<CLS> cls(mod, "NaNDerivateIslands", doc);
            cls.def_readwrite("riverwidth",  &CLS::riverwidth)
               .def_readwrite("islandwidth", &CLS::islandwidth)
               .def_readwrite("ratio",       &CLS::ratio)
               .def_readwrite("maxderivate", &CLS::maxderivate)
               .def_static(
                       "zscaledattributes", 
                        []() { return py::make_tuple("maxderivate"); }
               )
               .def(
                       "rescale", 
                        [](CLS const & self, float val)
                        {
                            auto cpy         = self;
                            cpy.maxderivate *= val;
                            return cpy;
                        }
               )
               .def("apply", [](CLS const & self, ndarray<float> arr)
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
            py::class_<CLS> cls(mod, "AberrantValuesRule", doc);
            cls.def_readwrite("constants",  &CLS::constants)
               .def_readwrite("derivative", &CLS::derivative)
               .def_readwrite("localnans",  &CLS::localnans)
               .def_readwrite("islands",    &CLS::islands)
               .def_static(
                       "zscaledattributes", 
                        []() {
                            return py::make_tuple(
                                "mindeltavalue", "maxabsvalue", "maxderivate", "cstmaxderivate"
                            ); 
                        }
               )
               .def(
                       "rescale", 
                        [](CLS const & self, float val)
                        {
                            auto cpy = self;
                            cpy.constants.mindeltavalue *= val;
                            cpy.derivative.maxabsvalue  *= val;
                            cpy.derivative.maxderivate  *= val;
                            cpy.islands.maxderivate     *= val;
                            return cpy;
                        }
               )
               .def("aberrant",
                    [](CLS const & self, ndarray<float> arr, bool clip, float ratio)
                    { 
                        float * data = arr.mutable_data();
                        size_t  sz   = arr.size();
                        size_t  cnt  = sz;
                        {
                            py::gil_scoped_release _;
                            self.apply(sz, data, clip);
                            for(size_t i = 0u; i < sz; ++i)
                                if(!std::isfinite(data[i]))
                                    --cnt;
                        }
                        return cnt < size_t(sz*ratio);
                    },
                    py::arg("beaddata"), py::arg("clip") = false, py::arg("ratio") = .8
                );
            _defaults(cls);
        }

        auto partial = dpx::pyinterface::make_namedtuple(mod, "Partial",
                "name",    "",
                "min",     ndarray<float>(0),
                "max",     ndarray<float>(0),
                "values",  ndarray<float>(0));

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

        {
            auto doc = R"_(Remove cycles with too few good points.

Good points are ones which have not been declared aberrant and which have
a finite value.)_";

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

        {
            auto doc = R"_(Remove cycles with too great a dynamic range.

The range of Z values is estimated using percentiles robustness purposes. It
is estimated from phases `PHASE.initial` to `PHASE.measure`.)_";

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

        {
            auto doc = R"_(Remove cycles which play ping-pong.

Some cycles are corrupted by close or passing beads, with the tracker switching
from one bead to another and back. This rules detects such situations by computing
the integral of the absolute value of the derivative of Z, first discarding values
below a givent threshold: those that can be considered due to normal levels of noise.)_";

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
        {
            auto doc = R"_(Remove cycles containing phase jumps.

Sometimes the tracking of a fringe may experience a phase-jump of 2π, usually when two fringes 
get too close to each other. This phase-jump will show as a ~1.4µm change of z,
often occuring as a rapid sequence of spikes.
This rule counts the number of such phase-jumps in a given cycle by counting the the number of
values of the absolute discrete derivative in the window (phasejumpheight ± delta).)_";

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
        {
            auto doc = R"_(Remove beads which don't have enough cycles ending at zero.

When too many cycles (> 90%) never reach 0 before the end of phase 5, the bead is
discarded. Such a case arises when:

* the hairpin never closes: the force is too high,
* a hairpin structure keeps the hairpin from closing. Such structures should be
detectable in ramp files.
* an oligo is blocking the loop.)_";

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
    }
}}

namespace cleaning { //module
    void pymodule(py::module & mod)
    {
        datacleaning::pymodule(mod);
        beadsubtraction::pymodule(mod);
    }
}
