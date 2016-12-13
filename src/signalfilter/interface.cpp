#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "signalfilter/signalfilter.h"
namespace signalfilter
{
    template<typename T, void (*run)(T, size_t, float*)>
    pybind11::array & _run(T const & self, pybind11::array_t<float> & input)
    {
        auto buf = input.request();
        (*run)(self, buf.size, (float*) buf.ptr);
        return input;
    }

    namespace forwardbackward
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args>(mod,"ForwardBackwardFilter")
                .def(pybind11::init<>())
                .def_readwrite("derivate",      &Args::derivate)
                .def_readwrite("normalize",     &Args::normalize)
                .def_readwrite("precision",     &Args::precision)
                .def_readwrite("window",        &Args::window)
                .def_readwrite("power",         &Args::power)
                .def_readwrite("estimators",    &Args::estimators)
                .def("__call__", _run<Args, run>)
                ;
        }
    };

    namespace nonlinear
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args>(mod, "NonLinearFilter")
                .def(pybind11::init<>())
                .def_readwrite("derivate",      &Args::derivate)
                .def_readwrite("precision",     &Args::precision)
                .def_readwrite("power",         &Args::power)
                .def_readwrite("estimators",    &Args::estimators)
                .def("__call__", _run<Args, run>)
                ;
        }
    };

    void pymodule(pybind11::module & mod)
    {
        forwardbackward::pymodule(mod);
        nonlinear      ::pymodule(mod);
    }
}
