#pragma once
#include "cleaning/interface/interface.h"
namespace cleaning::datacleaning { namespace {
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
}}
#include "cleaning/interface/datacleaning.h"
