#include <cmath>
#include <type_traits>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "cleaning/datacleaning.h"

namespace cleaning {
    template <typename T>
    inline T _get(char const * name, pybind11::dict & kwa, T deflt)
    { return  kwa.contains(name) ? kwa[name].cast<T>() : deflt; }

    template <typename T>
    inline void _get(T & inst, char const * name, pybind11::dict & kwa)
    {
        if(kwa.contains(name))
            inst = kwa[name].cast<T>();
    }

    template <typename T>
    inline void _get(T const & inst, char const * name, pybind11::dict & kwa)
    { kwa[name] = inst; }

    void _has(...) {}

    template <typename T>
    decltype(_has(&T::localnans))
    _fromkwa(T & inst, pybind11::dict kwa)
    {
        _get(inst.constants,    "constants",  kwa);
        _get(inst.derivative,   "derivative", kwa);
        _get(inst.localnans,    "localnans",  kwa);
        _get(inst.islands,      "islands",    kwa);
        if(!std::is_const<T>::value)
        {
            _fromkwa(inst.constants, kwa);
            _fromkwa(inst.derivative, kwa);
        }
    }

    template <typename T>
    decltype(_has(&T::riverwidth))
    _fromkwa(T & inst, pybind11::dict kwa)
    {
        _get(inst.riverwidth,  "riverwidth",  kwa);
        _get(inst.islandwidth, "islandwidth", kwa);
        _get(inst.ratio,       "ratio",       kwa);
        _get(inst.maxderivate, "maxderivate", kwa);
    }

    template <typename T>
    decltype(_has(&T::window, &T::ratio))
    _fromkwa(T & inst, pybind11::dict kwa)
    {
        _get(inst.window, "window", kwa);
        _get(inst.ratio,  "ratio",  kwa);
    }

    template <typename T>
    decltype(_has(&T::maxderivate, &T::maxabsvalue))
    _fromkwa(T & inst, pybind11::dict kwa)
    {
        _get(inst.maxderivate, "maxderivate", kwa);
        _get(inst.maxabsvalue, "maxabsvalue", kwa);
    }

    template <typename T>
    decltype(_has(&T::mindeltavalue, &T::mindeltarange))
    _fromkwa(T & inst, pybind11::dict kwa)
    {
        _get(inst.mindeltarange, "mindeltarange", kwa);
        _get(inst.mindeltavalue, "mindeltavalue", kwa);
    }

    template <typename T>
    pybind11::dict _getstate(T const & self)
    {
        pybind11::dict d;
        _fromkwa(self, d);
        return d;
    }

    template <typename T>
    std::unique_ptr<T> _setstate(pybind11::dict kwa)
    {
        std::unique_ptr<T> ptr(new T());
        _fromkwa(*ptr, kwa);
        return ptr;
    }

    template <typename T>
    std::unique_ptr<T> _init(pybind11::kwargs kwa)
    {
        std::unique_ptr<T> ptr(new T());
        _fromkwa(*ptr, kwa);
        return ptr;
    }

    template <typename T>
    void _defaults(pybind11::class_<T> & cls)
    {
        cls.def(pybind11::init(&_init<T>))
           .def("configure",  &_fromkwa<T>)
           .def(pybind11::pickle(&_getstate<T>, &_setstate<T>))
           ;
    }

    template <typename T>
    using ndarray = pybind11::array_t<T, pybind11::array::c_style>;

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
    }
}
