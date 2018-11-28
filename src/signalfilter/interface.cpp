#include <type_traits>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "signalfilter/signalfilter.h"
#include "signalfilter/accumulators.hpp"
namespace
{
    struct Check
    {
        bool err = false;
        bool operator () ();
    };
#   ifdef _MSC_VER
#       pragma warning( push )
#       pragma warning( disable : 4800)
#   endif
    bool Check::operator () () { return !(err || (err = PyErr_Occurred())); };
#   ifdef _MSC_VER
#       pragma warning( pop )
#   endif

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
        Check check;

        size_t sz = seq.size();
        est.estimators.resize(sz);
        for(size_t i = 0; i < sz && check(); ++i)
            est.estimators[i] = (size_t) (seq[i].cast<int>());
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
    void _fromkwa(T & inst, pybind11::kwargs kwa)
    {
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
    void _fromkwa<signalfilter::clip::Args>(signalfilter::clip::Args & inst,
                                            pybind11::kwargs kwa)
    {
        _get(inst.minval, "minval", kwa);
        _get(inst.maxval, "maxval", kwa);
    };

    template <typename T>
    std::unique_ptr<T> _init(pybind11::kwargs kwa)
    {
        std::unique_ptr<T> ptr(new T());
        _fromkwa(*ptr, kwa);
        return ptr;
    }

    template <typename T>
    std::unique_ptr<T> _setstate(pybind11::dict kwa)
    {
        std::unique_ptr<T> ptr(new T());
        _fromkwa(*ptr, kwa);
        return ptr;
    }

    template<typename T>
    pybind11::array & _run(T                  const & self,
                           pybind11::array_t<float> & inp,
                           pybind11::kwargs           kwa)
    {
        T cpy = self;
        _fromkwa(cpy, kwa);
        run(cpy, inp.size(), inp.mutable_data());
        return inp;
    }

    template <typename T, typename K>
    void    _apply(K & cls)
    {
        cls.def(pybind11::init(&_init<T>))
           .def_readwrite("derivate",  &T::derivate)
           .def_readwrite("power",     &T::power)
           .def_property("precision",  _get_prec<T>, _set_prec<T>)
           .def_property("estimators", _get_est<T>,  _set_est<T>)
           .def("__call__",            &_run<T>)
           ;
    }

    template <typename T>
    pybind11::dict _getdict(T const & p)
    {
        using namespace pybind11::literals;
        return pybind11::dict("derivate"_a   = p.derivate,
                              "precision"_a  = p.precision,
                              "power"_a      = p.power,
                              "estimators"_a = _get_est(p));
    };
}

namespace signalfilter {

    namespace forwardbackward
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args> cls(mod,"ForwardBackwardFilter");
            cls.def_readwrite("normalize",     &Args::normalize)
               .def_readwrite("window",        &Args::window)
               .def(pybind11::pickle([](Args const & p)
                                     {
                                         auto d = _getdict(p);
                                         d["normalize"] = p.normalize;
                                         d["window"]    = p.window;
                                         return d;
                                     },
                                     [](pybind11::dict d) { return _setstate<Args>(d); }))
               ;
            _apply<Args>(cls);
        }
    }

    namespace nonlinear
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args> cls(mod, "NonLinearFilter");
            cls.def(pybind11::pickle([](Args const & p) { return _getdict<Args>(p); },
                                     [](pybind11::dict d) { return _setstate<Args>(d); }))
               ;
            _apply<Args>(cls);
        }
    }

    namespace clip
    {
        void pymodule(pybind11::module & mod)
        {
            pybind11::class_<Args>(mod, "Clip")
                .def(pybind11::init(&_init<Args>))
                .def_readwrite("minval", &Args::minval)
                .def_readwrite("maxval", &Args::maxval)
                .def(pybind11::pickle([](Args const & p)
                                      {
                                          using namespace pybind11::literals;
                                          return pybind11::dict("minval"_a = p.minval,
                                                                "maxval"_a = p.maxval);
                                      },
                                     [](pybind11::dict d) { return _setstate<Args>(d); }))
                .def("__call__", &_run<Args>)
                ;
        }
    }
}

namespace signalfilter { namespace stats {
    template <typename T>
    T _nanfcn2(T (*fcn) (size_t, T const *),
               pybind11::array_t<T> & inp,
               pybind11::object & rng)
    {
        if(rng.is_none())
            return (*fcn)(inp.size(), inp.data());

        auto data = inp.data();
        int  size = int(inp.size());

        pybind11::int_ ii(0), jj(1);
        std::vector<T> meds;
        for(auto i = rng.begin(), e = rng.end(); i != e; ++i)
        {
            int i1 = pybind11::cast<int>((*i)[ii]);
            int i2 = pybind11::cast<int>((*i)[jj]);
            i1     = i1 <= -size ? 0 : i1 < 0 ? i1+size : i1;
            i2     = i2 <= -size ? 0 : i2 < 0 ? i2+size : i2;
            if(i2 <= i1 || i1 >= size)
                continue;
            auto x = fcn(i2-i1+1, data+i1);
            if(std::isfinite(x))
                meds.push_back(x);
        }
        return median(meds);
    }

    template <typename T>
    void _defhfsigma(pybind11::module & mod)
    {
        auto doc = R"_(Return the median of the absolute value of the
pointwise derivate of the signal. The median
itself is estimated using the P² quantile estimator
algorithm.)_";

        mod.def("nancount", [](pybind11::array_t<T> & inp, size_t width)
                    { 
                        pybind11::array_t<int>  arr(inp.size());
                        nancount(width, inp.size(), inp.data(), arr.mutable_data());
                        return arr;
                    }, doc);

        mod.def("nanthreshold", [](pybind11::array_t<T> & inp, size_t width, int threshold)
                    { 
                        pybind11::array_t<int>  arr(inp.size());
                        nanthreshold(width, threshold, inp.size(), inp.data(), arr.mutable_data());
                        return arr;
                    }, doc);

        mod.def("hfsigma", [](pybind11::array_t<T> & inp)
                    { return hfsigma(inp.size(), inp.data()); }, doc);
        mod.def("nanhfsigma", [](pybind11::array_t<T> & inp)
                    { return nanhfsigma(inp.size(), inp.data()); }, doc);
        mod.def("nanhfsigma", [](pybind11::array_t<T> & inp, pybind11::object rng)
                    { return _nanfcn2(&nanhfsigma<T>, inp, rng); }, doc);
        auto doc2 = R"_(Return the median of the absolute value of the
distance to the median for each point.)_";
        mod.def("mediandeviation", [](pybind11::array_t<T> & inp)
                    { return mediandeviation(inp.size(), inp.data()); }, doc2);
        mod.def("nanmediandeviation", [](pybind11::array_t<T> & inp)
                    { return nanmediandeviation(inp.size(), inp.data()); }, doc2);
        mod.def("nanmediandeviation", [](pybind11::array_t<T> & inp, pybind11::object rng)
                    { return _nanfcn2(&nanmediandeviation<T>, inp, rng); }, doc);
    }

    void pymodule(pybind11::module & mod)
    {
        auto smod       = mod.def_submodule("stats");
        _defhfsigma<float>(smod);
        _defhfsigma<double>(smod);
    }
}}

namespace signalfilter {
    void pymodule(pybind11::module & mod)
    {
        forwardbackward::pymodule(mod);
        nonlinear      ::pymodule(mod);
        clip           ::pymodule(mod);
        stats          ::pymodule(mod);
    }
}
