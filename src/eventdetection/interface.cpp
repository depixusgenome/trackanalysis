#include <string>
#include <type_traits>
#include <boost/preprocessor/stringize.hpp>
#include <boost/preprocessor/seq.hpp>
#include <boost/preprocessor/seq/cat.hpp>
#include <boost/preprocessor/seq/for_each.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "eventdetection/stattests.h"
#include "eventdetection/splitting.h"
#include "eventdetection/merging.h"
#define _DPX_TO_PP(_, CLS, ATTR) , _pp(BOOST_PP_STRINGIZE(ATTR), &CLS::ATTR)
#define DPX_PY2C(CLS, ATTRS) \
    _defaults<CLS>(mod, #CLS, doc BOOST_PP_SEQ_FOR_EACH(_DPX_TO_PP, CLS, ATTRS));

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

    template <typename T, typename K>
    struct PyPair
    {
        const char * name;
        K       T::* attr;
    };

    template <typename T, typename K>
    constexpr PyPair<T, K> _pp(char const * name, K T::*attr) { return {name, attr}; }

    template <typename T>
    inline void _get(T & inst, char const * name, pybind11::dict & kwa)
    {
        if(kwa.contains(name))
            inst = kwa[name].cast<T>();
    }

    template <typename T>
    inline void _get(T const & inst, char const * name, pybind11::dict & kwa)
    { kwa[name] = inst; }

    template <typename T, typename K>
    inline int _getpp(T const & inst, pybind11::dict & kwa, K arg)
    { _get(inst.*(arg.attr), arg.name, kwa); return 0; }

    template <typename T, typename K>
    inline int _getpp(T & inst, pybind11::dict & kwa, K arg)
    { _get(inst.*(arg.attr), arg.name, kwa); return 0; }

    void _has(...) {}

    template <typename T, typename ...Args> 
    inline void _getpp(T inst, pybind11::dict & kwa, Args ... args)
    { _has(_getpp(inst, kwa, args)...); }

    template <typename T>
    ndarray<int> _topyintervals(T && arr)
    {
        ndarray<int> out({long(arr.size()),   2l},
                         {long(2*sizeof(int)), long(sizeof(int)) });
        for(size_t i = 0u, e = arr.size(); i < e; ++i)
        {
            out.mutable_at(i, 0) = arr[i].first;
            out.mutable_at(i, 1) = arr[i].second;
        }
        return out;
    }

    template <typename T, typename ...Args>
    void _default_interface(pybind11::class_<T> & cls, Args ... args)
    {
        cls.def("__eq__",
                        [](pybind11::object & a, pybind11::object b) -> bool
                        { 
                            if(!a.attr("__class__").is(b.attr("__class__")))
                                return false;
                            return std::memcmp(a.cast<T*>(), b.cast<T*>(), sizeof(T)) == 0;
                        })
           .def("configure",
                        [args...](T const & self) -> pybind11::dict
                        { pybind11::dict d; _has(_getpp(self, d, args)...); return d; })
           .def(pybind11::pickle(
                        [args...](T const & self) -> pybind11::dict
                        { pybind11::dict d; _has(_getpp(self, d, args)...); return d; },
                        [args...](pybind11::dict d) -> T
                        {  T self; _has(_getpp(self, d, args)...); return self; }))
           ;
        auto add = [&cls](auto x) { cls.def_readwrite(x.name, x.attr); return 0; };
        _has(add(args)...);
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

namespace eventdetection { namespace splitting {
    template <typename T>
    ndarray<int> _call(T              const & self,
                       ndarray<float> const & pydata,
                       pybind11::object       pyprec)
    {
        if(pydata.size() == 0)
            return ndarray<int>({0l, 2l}, { long(2l*sizeof(int)), long(sizeof(int)) });
        
        float prec = pyprec.is_none() ? -1.0f : pyprec.cast<float>();
        data_t data({pydata.data(), pydata.size()});
        ints_t arr;
        {
            pybind11::gil_scoped_release _;
            arr = self.compute(prec, data);
        }
        return _topyintervals(arr);
    }

    template <typename T, typename ...Args>
    void _defaults(pybind11::module & mod, char const * name, char const *doc, Args ...args)
    {
        using namespace pybind11::literals;
        pybind11::class_<T> cls(mod, name, doc);
        cls.def(pybind11::init([args...](pybind11::kwargs d) -> std::unique_ptr<T>
                        {
                            std::unique_ptr<T> self;
                            _has(_getpp(*self, d, args)...);
                            return self; 
                        }))
           .def("__call__", &_call<T>, "data"_a, pybind11::arg("precision") = pybind11::none())
           .def_static("run", [args...](ndarray<float> data, pybind11::kwargs kwa)
                       {
                            pybind11::object prec;
                            if(kwa.contains("precision"))
                                prec = kwa["precision"];
                            T self;
                            _has(_getpp(self, kwa, args)...);
                            return _call(self, data, prec);
                       }, "data"_a);
         _default_interface(cls, args...);
    }

    void pymodule(pybind11::module & mod)
    {
        {
            auto doc = R"_(Detects flat stretches of value.

Flatness is defined pointwise: 2 points are flat if close enough one to the
other. This closeness is defined using a p-value for 2 points belonging to
the same normal distribution with a known sigma.

The precision is either provided or measured. In the latter case,
the estimation used is the median-deviation of the derivate of the data.)_";
            DPX_PY2C(DerivateSplitDetector,
                     (extensionwindow)(extensionratio)(gradewindow)(percentile)(distance))
        }
        {
            auto doc = R"_(Detects flat stretches of value.

Flatness is estimated using residues of a fit to the mean of the interval.)_";
            DPX_PY2C(ChiSquareSplitDetector,
                     (extensionwindow)(extensionratio)(gradewindow)(confidence))
        }
        {
            auto doc = R"_(Detects flat stretches of value.

Flatness is estimated using `DerivateSplitDetector`, then patched with
`ChiSquareSplitDetector` where no flat stretches were found for 5 or
more frames in a row.)_";
            DPX_PY2C(MultiGradeSplitDetector, (derivate)(chisquare)(minpatchwindow))
        }
    }
}}

namespace eventdetection { namespace merging {
    template <typename T>
    ndarray<int> _call(T              const & self,
                       ndarray<float> const & data,
                       ndarray<int>   const & intervals,
                       pybind11::args)
    {
        if(data.size() == 0)
            return ndarray<int>({0l, 2l}, { long(2l*sizeof(int)), long(sizeof(int)) });
        if(intervals.size() <= 1)
            return intervals;

        auto cr = intervals.unchecked<2>();
        ints_t ints(cr.shape(0));
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

        return int(ints.size()) == cr.shape(0) ? intervals : _topyintervals(ints);
    }

    template <typename T, typename ...Args>
    void _defaults(pybind11::module & mod, char const * name, char const *doc, Args ...args)
    {
        using namespace pybind11::literals;
        pybind11::class_<T> cls(mod, name, doc);
        cls.def(pybind11::init([args...](pybind11::kwargs d) -> std::unique_ptr<T>
                        {
                            std::unique_ptr<T> self;
                            _has(_getpp(*self, d, args)...);
                            return self; 
                        }))
           .def("__call__",   &_call<T>, "data"_a, "intervals"_a)
           .def_static("run", [args...](ndarray<float>   data,
                                        ndarray<int>     rng,
                                        pybind11::kwargs kwa)
                       {
                            T self;
                            _has(_getpp(self, kwa, args)...);
                            return _call(self, data, rng, pybind11::args());
                       }, "data"_a, "intervals"_a);
         _default_interface(cls, args...);
    }

    void pymodule(pybind11::module & mod)
    {
        {
            auto doc = R"_(Merges neighbouring stretches of data.

Two intervals are merged whenever the mean for the second cannot be
certified as being below that of the first. The p-value is estimated
considering that distributions for both stretches are normal with a possibly
different sigma.)_";
            DPX_PY2C(HeteroscedasticEventMerger, (confidence)(minprecision))
        }
        {
            auto doc = R"_(Merges neighbouring stretches of data if enough of)_"
                       R"_(their population have a common range.)_";
            DPX_PY2C(PopulationMerger, (percentile))
        }
        {
            auto doc = R"_(Merges neighbouring stretches of data if they share enough)_"
                       R"_(of a a common range.)_";
            DPX_PY2C(ZRangeMerger, (percentile))
        }
        {
            auto doc = R"_(Merges neighbouring stretches of data using:
* `HeteroscedasticEventMerger`: statistical test,
* `PopulationMerger`: a proportion of points in both stretches share a common range,
* `ZRangeMerger`: both stretches share enough of a common range.)_";
            DPX_PY2C(MultiMerger, (stats)(pop)(range))
        }
    }
}}

namespace eventdetection {
    void pymodule(pybind11::module & mod)
    {
        merging::pymodule(mod);
        samples::normal::pymodule(mod);
    }
}
