#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "signalfilter/signalfilter.h"
#include "signalfilter/stattests.h"
#include "signalfilter/accumulators.hpp"
namespace
{
    template<typename T>
    pybind11::array & _run(T const & self, pybind11::array_t<float> & inp)
    { run(self, inp.size(), inp.mutable_data()); return inp; }
}

namespace signalfilter {

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
                .def("__call__",                _run<Args>)
                ;
        }
    }

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
                .def("__call__", _run<Args>)
                ;
        }
    }

    namespace clip
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args>(mod, "Clip")
                .def(pybind11::init<>())
                .def_readwrite("minval", &Args::minval)
                .def_readwrite("maxval", &Args::maxval)
                .def("__call__", _run<Args>)
                ;
        }
    }
}

namespace pybind11 { namespace detail {
    template <> struct type_caster<samples::normal::Input> {
    public:
        using Input = samples::normal::Input;
        PYBIND11_TYPE_CASTER(Input, _("Input"));

        bool load(handle obj, bool)
        {
            pybind11::str const keys[3] = { "count", "mean", "sigma"};
            bool err   = false;
            auto check = [&err]() { return !(err || (err = PyErr_Occurred())); };

            pybind11::object   items[3];
            if(pybind11::isinstance<pybind11::sequence>(obj))
            {
                auto seq = pybind11::reinterpret_borrow<pybind11::sequence>(obj);
                for(size_t i = 0; i < 3 && check(); ++i)
                    items[i] = seq[i];
            } else if(pybind11::isinstance<pybind11::dict>(obj))
            {
                auto dico = pybind11::reinterpret_borrow<pybind11::dict>(obj);
                for(size_t i = 0; i < 3 &&  check(); ++i)
                    items[i] = dico[keys[i]];
            } else
                for(size_t i = 0; i < 3 &&  check(); ++i)
                    items[i] = obj.attr(keys[i]);

            if(check())
                value.count = items[0].cast<size_t>();
            if(check())
                value.mean  = items[1].cast<float>();
            if(check())
                value.sigma = items[2].cast<float>();

            return check();
        }

        static handle cast(Input src, return_value_policy, handle)
        { return make_tuple(src.count, src.mean, src.sigma); }
    };
}}

namespace samples { namespace normal {
    void pymodule(pybind11::module & mod)
    {
        auto smod  = mod.def_submodule("samples");
        auto nmod  = smod.def_submodule("normal");
        auto ksmod = nmod.def_submodule("knownsigma");
        ksmod.def("value",     knownsigma::value);
        ksmod.def("threshold", (float (*)(bool, float, float))
                                (knownsigma::threshold));
        ksmod.def("threshold", (float (*)(bool, float, float, size_t, size_t))
                                (knownsigma::threshold));
        ksmod.def("isequal",   knownsigma::isequal);

        auto hsmod = nmod.def_submodule("homoscedastic");
        hsmod.def("value",      homoscedastic::value);
        hsmod.def("islower",    homoscedastic::islower);
        hsmod.def("isgreater",  homoscedastic::isgreater);
        hsmod.def("isequal",    homoscedastic::isequal);

        auto ht = nmod.def_submodule("heteroscedastic");
        ht.def("value",         heteroscedastic::value);
        ht.def("islower",       heteroscedastic::islower);
        ht.def("isgreater",     heteroscedastic::isgreater);
        ht.def("isequal",       heteroscedastic::isequal);
    }
}}

namespace signalfilter { namespace stats {
    void pymodule(pybind11::module & mod)
    {
        auto smod  = mod.def_submodule("stats");
        smod.def("hfsigma", [](pybind11::array_t<float> & inp)
                            { return hfsigma(inp.size(), inp.data()); });
        smod.def("hfsigma", [](pybind11::array_t<double> & inp)
                            { return hfsigma(inp.size(), inp.data()); });
    }
}}

namespace signalfilter {
    void pymodule(pybind11::module & mod)
    {
        forwardbackward::pymodule(mod);
        nonlinear      ::pymodule(mod);
        clip           ::pymodule(mod);
        samples::normal::pymodule(mod);
        stats          ::pymodule(mod);
    }
}
