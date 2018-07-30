#include "cleaning/pybind11.hpp"
#include "eventdetection/stattests.h"
#include "eventdetection/splitting.h"
#include "eventdetection/merging.h"
#include "eventdetection/alignment.h"

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
    py::list _callall(T              const & self,
                      ndarray<float> const & pydata,
                      float                  prec,
                      ndarray<int>   const & pyfirst,
                      ndarray<int>   const & pylast
                     )
    {
        if(pydata.size() == 0)
            return py::list();
        
        float const * data  = pydata.data();
        int   const * first = pyfirst.data();
        int   const * last  = pylast.data();
        size_t        sz    = pyfirst.size();

        std::vector<ints_t> lst;
        {
            py::gil_scoped_release _;
            lst.reserve(sz);
            for(size_t i = 0u; i < sz; ++i)
                lst.emplace_back(self.compute(prec, {data+first[i], last[i]-first[i]}));
        }

        py::list pylst;
        for(auto const & i: lst)
            pylst.append(_topyintervals(i));
        return pylst;
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
        cls.def("__call__",   &_call<T>,     "data"_a, "precision"_a)
           .def("__call__",   &_callall<T>,  "data"_a, "precision"_a, "start"_a, "stop"_a)
           .def("grade",      &_grade<T>,    "data"_a, "precision"_a)
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
    pybind11::class_<T> _defaults(py::module & mod, char const * name, char const *doc, Args ...args)
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
        return cls;
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
        {
            auto doc = R"_(Filters flat stretches:

* clips the edges
* makes sure their length is enough.)_";
            auto cls = DPX_PY2C(EventSelector, (edgelength)(minlength))
            cls.def_property_readonly("minduration",
                                      [](EventSelector const & self)
                                      { return self.edgelength*2u+self.minlength; });
        }
    }
}}

namespace eventdetection  { namespace detector {
    using namespace splitting;
    using splitting::ints_t;
    struct EventDetector
    {
        splitting::MultiGradeSplitDetector split;
        merging::MultiMerger               merge;
        merging::EventSelector             select;

        ints_t compute(float precision, data_t const & data) const
        {
            auto ints = split.compute(precision, data);
            if(ints.size() > 1)
            {
                merge.run(std::get<0>(data), ints);
                if(ints.size() != 0)
                    select.run(std::get<0>(data), ints);
            }
            return ints;
        }
    };

    template <typename T, typename ...Args>
    void _defaults(py::module & mod, char const * name, char const *doc, Args ...args)
    {
        using namespace py::literals;
        py::class_<T> cls(mod, name, doc);
        cls.def("compute", &_call<T>,  "data"_a, "precision"_a);
        dpx::pyinterface::addapi<T>(cls, std::move(args)...);
    }

    void pymodule(py::module & mod)
    {
        auto doc = R"_(Detect, merge and select flat intervals in `PHASE.measure`.

# Attributes

* `split`: splits the data into too many intervals. This is based on a grade
computed for each frame indicating the likelihood that an event is finished.
See `eventdetection.splitting` for the available grades.

* `merge`: merges the previous intervals when the difference between their
population is not statistically relevant.

* `select`: possibly clips events and discards those too small.)_";
        detector::DPX_PY2C(EventDetector, (split)(merge)(select))
    }
}}

namespace eventdetection  { namespace alignment {
    template <typename T>
    ndarray<float> _call(T              const & self,
                         ndarray<float> const & data,
                         ndarray<int>   const & phase1,
                         ndarray<int>   const & phase2)
    {
        if(data.size() == 0 || phase1.size() == 0)
            return ndarray<float>();

        DataInfo info = { size_t(data.size()),   data.data(),
                          size_t(phase1.size()), phase1.data(), phase2.data()};
        info_t out;
        {
            py::gil_scoped_release _;
            out = self.compute(std::move(info));
        }

        ndarray<float> pyout(out.size());
        std::copy(std::begin(out), std::end(out), pyout.mutable_data());
        return pyout;
    }

    void _translate(bool del,
                    ndarray<float> const & delta,
                    ndarray<int>   const & phase,
                    ndarray<float>       & data)
    {
        if(data.size() == 0 || phase.size() == 0)
            return;

        DataInfo info = { size_t(data.size()),  delta.data(),
                          size_t(phase.size()), phase.data(), nullptr};
        auto ptrdata(data.mutable_data());
        {
            py::gil_scoped_release _;
            translate(std::move(info), del, ptrdata);
        }
    }

    void _medianthreshold(float minv,
                          ndarray<float> const & data,
                          ndarray<int>   const & phase1,
                          ndarray<int>   const & phase2,
                          ndarray<float>       & bias)
    {
        if(data.size() == 0 || phase1.size() == 0)
            return;

        DataInfo info = { size_t(data.size()),   data.data(),
                          size_t(phase1.size()), phase1.data(), phase2.data()};
        auto ptrdata(bias.mutable_data());
        {
            py::gil_scoped_release _;
            medianthreshold(std::move(info), minv, ptrdata);
        }
    }

    template <typename T, typename ...Args>
    void _defaults(py::module & mod, char const * name, char const *doc, Args ...args)
    {
        using namespace pybind11::literals;
        py::class_<T> cls(mod, name, doc);
        cls.def("compute", &_call<T>, "data"_a, "phase1"_a, "phase2"_a);
        dpx::pyinterface::addapi<T>(cls, std::move(args)...);
    }

    void pymodule(py::module & mod)
    {
#       define DPX_AL_ENUM(CLS, X, Y)               \
            py::enum_<CLS::Mode>(mod, #CLS"Mode")   \
                .value(#X, CLS::Mode::X)            \
                .value(#Y, CLS::Mode::Y)            \
                .export_values();
        {
            auto doc = R"_(Functor which an array of biases computed as the extremum
of provided ranges.

Biases are furthermore centered at zero around their median.

Attributes:

* *window*: the width on which to compute a median.
* *edge*: the edge to use: left or right)_";

            DPX_AL_ENUM(PhaseEdgeAlignment,left,right)
            DPX_PY2C(PhaseEdgeAlignment, (window)(mode)(percentile))
        }

        {
            auto doc = R"_(Functor which an array of biases computed as the
extremum of provided ranges.

Biases are furthermore centered at zero around their median

Attributes:

* *mode*: the extremum to use
* *binsize*: if > 2, the extremum is computed over the median of values binned
by *binsize*.)_";

            DPX_AL_ENUM(ExtremumAlignment,min,max)
            DPX_PY2C(ExtremumAlignment, (binsize)(mode))
        }

        using namespace pybind11::literals;
        mod.def("translate", &_translate,
                "deleteonnan"_a, "deltas"_a, "phase"_a, "data"_a);
        mod.def("medianthreshold", &_medianthreshold,
                "minv"_a, "data"_a, "phase1"_a, "phase2"_a, "bias"_a);
    }
}}

namespace eventdetection {
    void pymodule(py::module & mod)
    {
        samples::normal::pymodule(mod);
        merging::pymodule(mod);
        splitting::pymodule(mod);
        detector::pymodule(mod);
        alignment::pymodule(mod);
    }
}
