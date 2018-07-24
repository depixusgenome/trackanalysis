#include <boost/preprocessor/seq/for_each_product.hpp> 
#include <boost/preprocessor/seq/to_tuple.hpp>
#include <boost/preprocessor/tuple/elem.hpp> 
#include "cleaning/pybind11.hpp"
#include "eventdetection/stattests.h"
#include "eventdetection/splitting.h"
#include "eventdetection/merging.h"

using dpx::pyinterface::ndarray;
namespace 
{
    inline ndarray<int> _topyintervals()
    { return ndarray<int>({0l, 2l}, { long(2l*sizeof(int)), long(sizeof(int)) }); }

    template <typename T>
    inline ndarray<int> _topyintervals(T && arr)
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
}
namespace samples { namespace normal {
    struct SimpleInput : public Input { using Input::Input; };
}}

namespace pybind11 { namespace detail {
    using dpx::pyinterface::Check;
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

namespace py = pybind11;
namespace samples { namespace normal {
    namespace 
    {
        ndarray<float> _valuekn(bool iseq, py::array arr)
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
        ndarray<float> _value(py::array arr)
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

    void pymodule(py::module & mod)
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
                       float                  prec)
    {
        if(pydata.size() == 0)
            return _topyintervals();
        
        data_t data({pydata.data(), pydata.size()});
        ints_t arr;
        {
            py::gil_scoped_release _;
            arr = self.compute(prec, data);
        }
        return _topyintervals(arr);
    }

    template <typename T>
    ndarray<float> _grade(T              const & self,
                          ndarray<float> const & pydata,
                          float                  prec)
    {
        if(pydata.size() == 0)
            return ndarray<float>(0l);
        
        grade_t arr(pydata.data(), pydata.size());
        {
            py::gil_scoped_release _;
            self.grade(prec, arr);
        }
        return dpx::pyinterface::toarray(arr);
    }

    template <typename T>
    struct _threshold;

    template <>
    struct _threshold<MultiGradeSplitDetector>
    {
        static py::none call(MultiGradeSplitDetector const &) { return {}; }
    };

    template <>
    struct _threshold<ChiSquareSplitDetector>
    {
        static float call(ChiSquareSplitDetector const & self, float precision)
        { return self.threshold(precision); }
    };

    template <>
    struct _threshold<DerivateSplitDetector>
    {
        static float call(DerivateSplitDetector const & self,
                          ndarray<float>        const & pydata,
                          float                         precision)
        {
            grade_t arr(pydata.data(), pydata.size());
            return self.threshold(precision, arr);
        }
    };

    template <typename T, typename ...Args>
    void _defaults(py::module & mod, char const * name, char const *doc, Args ...args)
    {
        using namespace py::literals;
        py::class_<T> cls(mod, name, doc);
        cls.def("__call__",   &_call<T>,  "data"_a, "precision"_a)
           .def("grade",      &_grade<T>, "data"_a, "precision"_a)
           .def("threshold",  &_threshold<T>::call)
           .def_static("run", [args...](ndarray<float> data, float prec, py::kwargs kwa)
                       {
                            auto self = dpx::pyinterface::create<T>(kwa, args...);
                            return _call(*self, data, prec);
                       }, "data"_a, "precision"_a);
        dpx::pyinterface::addapi<T>(cls, std::move(args)...);
    }

    void pymodule(py::module & mod)
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
                       py::args)
    {
        if(data.size() == 0)
            return _topyintervals();
        if(intervals.size() <= 1)
            return intervals;

        auto cr = intervals.unchecked<2>();
        ints_t ints(cr.shape(0));
        auto sz = data.size();
        for(int i = 0, e = cr.shape(0); i < e; ++i)
        {
            if(cr(i, 0) < 0 || cr(i, 0) > sz || cr(i, 1) < 0 || cr(i, 1) > sz)
                throw py::index_error();
            ints[i] = {cr(i,0), cr(i, 1)};
        }

        float const * arr = data.data();
        {
            py::gil_scoped_release _;
            self.run(arr, ints);
        }

        return int(ints.size()) == cr.shape(0) ? intervals : _topyintervals(ints);
    }

    template <typename T, typename ...Args>
    void _defaults(py::module & mod, char const * name, char const *doc, Args ...args)
    {
        using namespace py::literals;
        py::class_<T> cls(mod, name, doc);
        cls.def("__call__",   &_call<T>, "data"_a, "intervals"_a)
           .def_static("run", [args...](ndarray<float>   data,
                                        ndarray<int>     rng,
                                        py::kwargs kwa)
                       {
                            auto self = dpx::pyinterface::create<T>(kwa, args...);
                            return _call(*self, data, rng, py::args());
                       }, "data"_a, "intervals"_a);
        dpx::pyinterface::addapi(cls, std::move(args)...);
    }

    void pymodule(py::module & mod)
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

namespace 
{
    template <typename T1, typename T2>
    ndarray<int> _events(T1 const & split, T2 const & merge,
                         ndarray<float>       const & pydata,
                         float                        precision)
    {
        if(pydata.size() == 0)
            return _topyintervals();
        
        eventdetection::splitting::data_t data({pydata.data(), pydata.size()});
        eventdetection::splitting::ints_t ints;
        {
            py::gil_scoped_release _;
            ints = split.compute(precision, data);

            if(ints.size() > 1)
                merge.run(std::get<0>(data), ints);
        }

        return _topyintervals(ints);
    }
}
namespace eventdetection {
    void pymodule(py::module & mod)
    {
        merging::pymodule(mod);
        splitting::pymodule(mod);
        samples::normal::pymodule(mod);
#       define __DPX_EVTS_ALL(X,Y)                                          \
            mod.def("events", &_events<splitting::X,merging::Y>,            \
                    "splitter"_a, "merger"_a, "data"_a, "precision"_a);

#       define _DPX_EVTS_ALL(X)                                             \
            __DPX_EVTS_ALL(BOOST_PP_TUPLE_ELEM(2, 0, X), BOOST_PP_TUPLE_ELEM(2, 1, X))
#       define DPX_EVTS_ALL(_, ITMS) _DPX_EVTS_ALL(BOOST_PP_SEQ_TO_TUPLE(ITMS))
        using namespace py::literals;
        BOOST_PP_SEQ_FOR_EACH_PRODUCT(DPX_EVTS_ALL,
                                      ((DerivateSplitDetector)
                                       (ChiSquareSplitDetector)(MultiGradeSplitDetector))
                                      ((HeteroscedasticEventMerger)
                                       (PopulationMerger)(ZRangeMerger)(MultiMerger)))
    }
}
