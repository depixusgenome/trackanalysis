#pragma once
#include "cleaning/interface/interface.h"
namespace cleaning::datacleaning { namespace  {
    template <typename T>
    inline T _toptr(py::dict kwa)
    {
        T itm;
        _fromkwa<T>(itm, kwa);
        return itm;
    }


    template <typename T>
    inline py::dict _getkwa(T const & inst) 
    { 
        py::dict d;
        _fromkwa<T const>(inst, d);
        return d; 
    }

    inline py::tuple _totuple(py::object cls, const char * name, DataOutput const & out)
    {
        auto cnv = [](auto x) { return ndarray<typename decltype(x)::value_type>(x.size(), x.data()); };
        auto x1  = cnv(out.minv), x2 = cnv(out.maxv); auto x3 = cnv(out.values);
        return cls(name, x1, x2, x3);
    }

    inline DataInfo _toinput(ndarray<float> bead, ndarray<int> phase1, ndarray<int> phase2)
    { return { size_t(bead.size()), bead.data(),
               size_t(phase1.size()), phase1.data(), phase2.data() }; }

    template <typename T, typename ...K>
    inline DataOutput __applyrule(T const & self, K && ... info)
    {
        py::gil_scoped_release _;
        return self.apply(info...);
    }

    template <typename T>
    inline void _defaults(py::class_<T> & cls)
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
        // pybind11 bug?
        setattr(cls, "__setstate__", getattr(cls, "configure"));
    }
}}
