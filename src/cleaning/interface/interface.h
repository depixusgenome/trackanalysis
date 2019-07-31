#pragma once
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

    inline void _has(...) {}


    template <typename T, typename K1, typename K2>
    inline void _pairproperty(py::class_<T> & cls, char const * name, K1 T::*first, K2  T::*second)
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
