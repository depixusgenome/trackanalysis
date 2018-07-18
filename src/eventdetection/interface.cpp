#include <string>
#include <type_traits>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "eventdetection/stattests.h"
#include "eventdetection/merging.h"

namespace {
    template <typename T>
    using ndarray = pybind11::array_t<T, pybind11::array::c_style>;

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
            Check check;

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
            Check check;

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
    namespace 
    {
        ndarray<float> _valuekn(bool iseq, pybind11::array arr)
        {
            if(arr.shape()[0] == 0)
                return ndarray<float>(0);

            ndarray<float> out(arr.shape()[0]-1);
            float * res = out.mutable_data();
            for(size_t i = 0, end = arr.shape()[0]-1; i < end; ++i)
            {
                int   const * data  = (int const *) arr.data(i);
                float const * fdata = (float const *) (data+1);
                Input         left  = {size_t(*data), *fdata, 0.f};

                data        = (int   const *) arr.data(i+1);
                fdata       = (float const *) (data+1);
                Input right = {size_t(*data), *fdata, 0.f};
                res[i] = knownsigma::value(iseq, left, right);
            }
            return out;
        }

        template <float (*FCN)(Input const &, Input const &)>
        ndarray<float> _value(pybind11::array arr)
        {
            if(arr.shape()[0] == 0)
                return ndarray<float>(0);

            ndarray<float> out(arr.shape()[0]-1);
            float * res = out.mutable_data();
            for(size_t i = 0, end = arr.shape()[0]-1; i < end; ++i)
            {
                int   const * data  = (int const *) arr.data(i);
                float const * fdata = (float const *) (data+1);
                Input         left  = {size_t(*data), fdata[0], fdata[1]};

                data        = (int   const *) arr.data(i+1);
                fdata       = (float const *) (data+1);
                Input right = {size_t(*data), fdata[0], fdata[1]};
                res[i] = FCN(left, right);
            }
            return out;
        }
    }

    void pymodule(pybind11::module & mod)
    {
        auto smod  = mod.def_submodule("samples");
        auto nmod  = smod.def_submodule("normal");
        auto ksmod = nmod.def_submodule("knownsigma");
        ksmod.def("value",     [](bool a, SimpleInput const & b, SimpleInput const & c)
                               { return knownsigma::value(a,b,c); });
        ksmod.def("value",     _valuekn);
        ksmod.def("threshold", (float (*)(bool, float, float))
                                (knownsigma::threshold));
        ksmod.def("threshold", (float (*)(bool, float, float, size_t, size_t))
                                (knownsigma::threshold));
        ksmod.def("isequal",   knownsigma::isequal);

        auto hsmod = nmod.def_submodule("homoscedastic");
        hsmod.def("value",      homoscedastic::value);
        hsmod.def("threshold",  homoscedastic::threshold);
        hsmod.def("thresholdvalue", homoscedastic::tothresholdvalue);
        hsmod.def("thresholdvalue", _value<homoscedastic::tothresholdvalue>);
        hsmod.def("islower",    homoscedastic::islower);
        hsmod.def("isgreater",  homoscedastic::isgreater);
        hsmod.def("isequal",    homoscedastic::isequal);

        auto ht = nmod.def_submodule("heteroscedastic");
        ht.def("value",         heteroscedastic::value);
        ht.def("threshold",  heteroscedastic::threshold);
        ht.def("thresholdvalue", heteroscedastic::tothresholdvalue);
        ht.def("thresholdvalue", _value<heteroscedastic::tothresholdvalue>);
        ht.def("islower",       heteroscedastic::islower);
        ht.def("isgreater",     heteroscedastic::isgreater);
        ht.def("isequal",       heteroscedastic::isequal);
    }
}}

namespace eventdetection { namespace merging {
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
    decltype(_has(&T::confidence, &T::minprecision))
    _fromkwa(T & inst, pybind11::dict kwa)
    {
        _get(inst.confidence,   "confidence",   kwa);
        _get(inst.minprecision, "minprecision", kwa);
    }

    template <typename T>
    decltype(_has(&T::stats))
    _fromkwa(T & inst, pybind11::dict kwa)
    {
        _get(inst.stats, "stats", kwa);
        _get(inst.pop,   "pop",   kwa);
        _get(inst.range, "range", kwa);
    }

    template <typename T>
    decltype(_has(&T::percentile))
    _fromkwa(T & inst, pybind11::dict kwa)
    { _get(inst.percentile, "percentile", kwa); }

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
    ndarray<int> _call(T              const & self,
                       ndarray<float> const & data,
                       ndarray<int>   const & intervals)
    {
        if(data.size() == 0)
        {
            std::vector<size_t> shape   = {0, 2};
            std::vector<size_t> strides = { shape[1]*sizeof(int), sizeof(int) };
            return ndarray<int>(shape, strides);
        }
        if(intervals.size() <= 1)
            return intervals;

        auto cr = intervals.unchecked<2>();
        INTERVALS ints(cr.shape(0));
        auto sz = data.size();
        for(int i = 0, e = cr.shape(0); i < e; ++i)
        {
            if(cr(i, 0) < 0 || cr(i, 0) > sz || cr(i, 1) < 0 || cr(i, 1) > sz)
                throw pybind11::index_error();
            ints[i] = {cr(i,0), cr(i, 1)};
        }

        float const * arr = data.data();
        {
            pybind11::gil_scoped_release _;
            self.run(arr, ints);
        }
        if(int(ints.size()) == cr.shape(0))
            return intervals;

        ndarray<int> out({long(ints.size()),   long(2)},
                         {long(2*sizeof(int)), long(sizeof(int)) });
        for(size_t i = 0u, e = ints.size(); i < e; ++i)
        {
            out.mutable_at(i, 0) = ints[i].first;
            out.mutable_at(i, 1) = ints[i].second;
        }
        return out;
    }

    template <typename T>
    ndarray<int> _run(ndarray<float> data, ndarray<int> ints, pybind11::kwargs kwa)
    {
        T self;
        _fromkwa(self, kwa);
        return _call(self, data, ints);
    }

    template <typename T>
    void _defaults(pybind11::class_<T> & cls)
    {
        cls.def(pybind11::init(&_init<T>))
           .def("__call__",   &_call<T>)
           .def_static("run", &_run<T>)
           .def("configure",  &_fromkwa<T>)
           .def(pybind11::pickle(&_getstate<T>, &_setstate<T>))
           ;
    }

    void _pystats(pybind11::module & mod)
    {
        using CLS = HeteroscedasticEventMerger;
        pybind11::class_<CLS> cls(mod,"HeteroscedasticEventMerger");
        cls.def_readwrite("confidence",   &CLS::confidence)
           .def_readwrite("minprecision", &CLS::minprecision)
           ;
        _defaults(cls);
    }

    template<typename CLS, typename K>
    void _pyrange(pybind11::module & mod, K name)
    {
        pybind11::class_<CLS> cls(mod, name);
        cls.def_readwrite("percentile", &CLS::percentile);
        _defaults(cls);
    }

    void _pymulti(pybind11::module & mod)
    {
        using CLS = MultiMerger;
        pybind11::class_<CLS> cls(mod, "MultiMerger");
        cls.def_readwrite("stats", &CLS::stats)
           .def_readwrite("pop",   &CLS::pop)
           .def_readwrite("range", &CLS::range)
           ;
        _defaults(cls);
    }

    void pymodule(pybind11::module & mod)
    {
      _pystats(mod);
      _pyrange<PopulationMerger>(mod,"PopulationMerger");
      _pyrange<ZRangeMerger>(mod, "ZRangeMerger");
      _pymulti(mod);
    }
}}

namespace eventdetection {
    void pymodule(pybind11::module & mod)
    {
        merging::pymodule(mod);
        samples::normal::pymodule(mod);
    }
}
