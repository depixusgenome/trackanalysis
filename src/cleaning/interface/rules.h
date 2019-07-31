#pragma once
#include "cleaning/interface/interface.h"
namespace cleaning::datacleaning { namespace { // fromkwa specializations
    template <typename T>
    inline typename issame<T, SaturationRule>::type
    _fromkwa(T & inst, py::dict & kwa)
    {
        _get(std::is_const<T>(), inst.maxv,          "maxsaturation", kwa);
        _get(std::is_const<T>(), inst.maxdisttozero, "maxdisttozero", kwa);
        _get(std::is_const<T>(), inst.satwindow,     "satwindow",     kwa);
    };

    template <typename T>
    inline typename issame<T, PingPongRule>::type
    _fromkwa(T & inst, py::dict & kwa)
    {
        _get(std::is_const<T>(), inst.maxv,          "maxpingpong",   kwa);
        _get(std::is_const<T>(), inst.mindifference, "mindifference", kwa);
        _get(std::is_const<T>(), inst.minpercentile, inst.maxpercentile, "percentiles", kwa);
    }

    template <typename T>
    inline typename issame<T, PhaseJumpRule>::type
    _fromkwa(T & inst, py::dict & kwa)
    {
        _get(std::is_const<T>(), inst.maxv,             "maxphasejump",     kwa);
        _get(std::is_const<T>(), inst.phasejumpheight,  "phasejumpheight",  kwa);
        _get(std::is_const<T>(), inst.delta,            "delta",            kwa);
    }

    template <typename T>
    inline typename issame<T, PopulationRule>::type
    _fromkwa(T & inst, py::dict & kwa)
    { _get(std::is_const<T>(), inst.minv,    "minpopulation",  kwa); }

    template <typename T>
    inline typename issame<T, HFSigmaRule>::type
    _fromkwa(T & inst, py::dict & kwa)
    {
        _get(std::is_const<T>(), inst.minv,    "minhfsigma",  kwa);
        _get(std::is_const<T>(), inst.maxv,    "maxhfsigma",  kwa);
    }

    template <typename T>
    inline typename issame<T, ExtentRule>::type
    _fromkwa(T & inst, py::dict & kwa)
    {
        _get(std::is_const<T>(), inst.minv,    "minextent",  kwa);
        _get(std::is_const<T>(), inst.maxv,    "maxextent",  kwa);
        _get(std::is_const<T>(), inst.minpercentile, inst.maxpercentile, "percentiles", kwa);
    }
}}
#include "cleaning/interface/datacleaning.h"
