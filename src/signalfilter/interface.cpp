#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "signalfilter/signalfilter.h"
#include "signalfilter/stattests.h"
namespace
{
    template<typename T>
    pybind11::array & _run(T const & self, pybind11::array_t<float> & input)
    {
        auto buf = input.request();
        run(self, buf.size, (float*) buf.ptr);
        return input;
    }
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
            bool err   = false;
            auto check = [&err]() { return !(err || (err = PyErr_Occurred())); };

            pybind11::object   items[3];

            pybind11::sequence seq(obj, true);
            if(seq.check())
                for(size_t i = 0; i < 3 && check(); ++i)
                    items[i] = seq[i];
            else
            {
                pybind11::str keys[3] = { "count", "mean", "sigma"};
                pybind11::dict dico(obj, true);
                if(dico.check())
                    for(size_t i = 0; i < 3 &&  check(); ++i)
                        items[i] = dico[keys[i]];
                else
                    for(size_t i = 0; i < 3 &&  check(); ++i)
                        items[i] = obj.attr(keys[i]);
            }

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

namespace signalfilter {
    void pymodule(pybind11::module & mod)
    {
        forwardbackward::pymodule(mod);
        nonlinear      ::pymodule(mod);
        clip           ::pymodule(mod);
        samples::normal::pymodule(mod);
    }
}
