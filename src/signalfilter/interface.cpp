#include <type_traits>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "signalfilter/signalfilter.h"
#include "signalfilter/stattests.h"
#include "signalfilter/accumulators.hpp"

namespace
{

    template <typename T>
    pybind11::object _get_prec(T const & est)
    { return est.precision <= 0. ? pybind11::object() : pybind11::cast(est.precision); }

    template <typename T>
    void _set_prec(T & est, pybind11::object obj)
    {
        if(obj.is_none())
            est.precision = 0.;
        else
            est.precision = pybind11::cast<float>(obj);
    }

    template <typename T>
    pybind11::object _get_est(T const & est)
    {
        pybind11::tuple tup(est.estimators.size());
        for(size_t i = 0, e = est.estimators.size(); i < e; ++i)
            tup[i] = int(est.estimators[i]);
        return tup;
    }

    template <typename T>
    void _set_est(T & est, pybind11::object obj)
    {
        auto seq = pybind11::reinterpret_borrow<pybind11::sequence>(obj);
        bool err   = false;
        auto check = [&err]() { return !(err || (err = PyErr_Occurred())); };

        est.estimators.resize(seq.size());
        for(size_t i = 0; i < est.estimators.size() && check(); ++i)
            est.estimators[i] = seq[i].cast<size_t>();
    }

    template <typename T>
    void _get(T & inst, char const * name, pybind11::dict & kwa)
    {
        if(kwa.contains(name)) 
            inst = kwa[name].cast<T>();
    }

    template <typename T>
    void _init_other(T &, pybind11::dict) {}

    void _init_other(signalfilter::forwardbackward::Args & inst,
                     pybind11::dict kwa) 
    {
        _get(inst.normalize, "normalize", kwa);
        _get(inst.window,    "window", kwa);
    }

    template <typename T>
    void _init(T & inst, pybind11::kwargs kwa)
    {
        new (&inst) T();
        _get(inst.derivate, "derivate",     kwa);
        _get(inst.power,    "power",        kwa);
        if(kwa.contains("precision"))
            _set_prec(inst, kwa["precision"]);
        _get(inst.derivate, "derivate",    kwa);
        if(kwa.contains("estimators"))
            _set_est(inst, kwa["estimators"]);
        _init_other(inst, kwa);
    };

    template <>
    void _init<signalfilter::clip::Args>(signalfilter::clip::Args & inst,
                                         pybind11::kwargs kwa)
    {
        new (&inst) signalfilter::clip::Args();
        _get(inst.minval, "minval", kwa);
        _get(inst.maxval, "maxval", kwa);
    };

    template<typename T>
    pybind11::array & _run(T                  const & self,
                           pybind11::array_t<float> & inp,
                           pybind11::kwargs           kwa)
    { 
        T cpy = self;
        _init(cpy, kwa);
        run(cpy, inp.size(), inp.mutable_data());
        return inp;
    }

    template <typename T, typename K>
    void    _apply(K & cls)
    {
        cls.def("__init__", &_init<T>)
           .def_readwrite("derivate",  &T::derivate)
           .def_readwrite("power",     &T::power)
           .def_property("precision",  _get_prec<T>, _set_prec<T>)
           .def_property("estimators", _get_est<T>,  _set_est<T>)
           .def("__call__",            &_run<T>)
           ;
    }
}

namespace signalfilter {

    namespace forwardbackward
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args> cls(mod,"ForwardBackwardFilter");
            cls.def_readwrite("normalize",     &Args::normalize)
               .def_readwrite("window",        &Args::window)
               .def("__getstate__",        [](Args const &p) 
                    { 
                        return pybind11::make_tuple(p.derivate, p.precision, p.power,
                                                   _get_est(p), p.normalize, p.window);
                    })
               .def("__setstate__",        [](Args &p, pybind11::tuple t)
                    { 
                        if (t.size() != 6)
                            throw std::runtime_error("Invalid state!");
                        new (&p) Args();
                        int i = 0;
                        auto set = [&](auto & x)
                                { 
                                    using tpe = typename std::remove_reference<decltype(x)>::type;
                                    x = t[i++].cast<tpe>();
                                };
                        set(p.derivate);
                        set(p.precision);
                        set(p.power);
                        _set_est(p, t[i++]);
                        set(p.normalize);
                        set(p.window);
                    })
               ;

            _apply<Args>(cls);
        }
    }

    namespace nonlinear
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args> cls(mod, "NonLinearFilter");
            cls.def("__getstate__",        [](const Args &p) 
                    { 
                        return pybind11::make_tuple(p.derivate, p.precision, p.power,
                                                   _get_est(p));
                    })
               .def("__setstate__",        [](Args &p, pybind11::tuple t)
                    { 
                        if (t.size() != 4)
                            throw std::runtime_error("Invalid state!");
                        new (&p) Args();
                        int i = 0;
                        auto set = [&](auto & x)
                                { 
                                    using tpe = typename std::remove_reference<decltype(x)>::type;
                                    x = t[i++].cast<tpe>();
                                };
                        set(p.derivate);
                        set(p.precision);
                        set(p.power);
                        _set_est(p, t[i++]);
                    })
               ;
            _apply<Args>(cls);
        }
    }

    namespace clip
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args>(mod, "Clip")
                .def("__init__", &_init<Args>)
                .def_readwrite("minval", &Args::minval)
                .def_readwrite("maxval", &Args::maxval)
                .def("__call__", &_run<Args>)
                ;
        }
    }
}

namespace samples { namespace normal {
    struct SimpleInput : public Input { using Input::Input; };
}}

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

    template <> struct type_caster<samples::normal::SimpleInput> {
    public:
        using Input = samples::normal::SimpleInput;
        PYBIND11_TYPE_CASTER(Input, _("SimpleInput"));

        bool load(handle obj, bool)
        {
            pybind11::str const keys[2] = { "count", "mean"};
            bool err   = false;
            auto check = [&err]() { return !(err || (err = PyErr_Occurred())); };

            pybind11::object   items[2];
            if(pybind11::isinstance<pybind11::sequence>(obj))
            {
                auto seq = pybind11::reinterpret_borrow<pybind11::sequence>(obj);
                for(size_t i = 0; i < 2 && check(); ++i)
                    items[i] = seq[i];
            } else if(pybind11::isinstance<pybind11::dict>(obj))
            {
                auto dico = pybind11::reinterpret_borrow<pybind11::dict>(obj);
                for(size_t i = 0; i < 2 &&  check(); ++i)
                    items[i] = dico[keys[i]];
            } else
                for(size_t i = 0; i < 2 &&  check(); ++i)
                    items[i] = obj.attr(keys[i]);

            if(check())
                value.count =  items[0].cast<size_t>();
            if(check())
                value.mean  = items[1].cast<float>();
            value.sigma = 0.f;
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
        ksmod.def("value",     [](bool a, SimpleInput const & b, SimpleInput const & c)
                               { return knownsigma::value(a,b,c); });
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
        smod.def("mediandeviation", [](pybind11::array_t<float> & inp)
                            { return mediandeviation(inp.size(), inp.data()); });
        smod.def("mediandeviation", [](pybind11::array_t<double> & inp)
                            { return mediandeviation(inp.size(), inp.data()); });
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
