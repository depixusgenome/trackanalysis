#include "utils/pybind11.hpp"
#include "peakfinding/peakfinding.h"
#include "peakfinding/projection.h"
using dpx::pyinterface::ndarray;
using dpx::pyinterface::toarray;
namespace py = pybind11;

namespace peakfinding { namespace projection {
    Digitizer _digit(CyclesDigitization const & self,
                     float                      prec,
                     ndarray<float>     const & pydata,
                     ndarray<int>       const & pyfirst,
                     ndarray<int>       const & pylast)
    {
        std::vector<std::pair<size_t, float const *>> data;
        for(size_t i = 0, ie = pyfirst.size(); i < ie; ++i)
            data.emplace_back(pylast.data()[i]-pyfirst.data()[i],
                              pydata.data()+pyfirst.data()[i]);

        return DPX_GIL_SCOPED(self.compute(prec, data));
    }

    ndarray<float> _call(CycleProjection const & self,
                         Digitizer       const & digitizer,
                         ndarray<float>  const & pydata)
    {
        auto sz   = pydata.size();
        auto data = pydata.data();
        return toarray(digitizer.nbins,
                       [&]() {
                           auto dig = digitizer.compute(sz, data);
                           return self.compute(dig);
                       });
    }

    cycles_t _cycles(ndarray<float>  const & pydata,
                     ndarray<int>    const & pyfirst,
                     ndarray<int>    const & pylast)
    {
        cycles_t data;
        for(size_t i = 0u, ie = pyfirst.size(); i < ie; ++i)
            data.emplace_back(pylast.data()[i]-pyfirst.data()[i],
                              pydata.data() + pyfirst.data()[i]);
        return data;
    }


    ndarray<float> _callall(CycleProjection const & self,
                            Digitizer       const & digitizer,
                            ndarray<float>  const & pydata,
                            ndarray<int>    const & pyfirst,
                            ndarray<int>    const & pylast)
    {
        if(pydata.size() == 0 ||  pyfirst.size() == 0)
            return py::list();

        auto data = _cycles(pydata, pyfirst, pylast);
        long szf  = long(sizeof(float));
        ndarray<float> out(
                {data.size(), digitizer.nbins},
                {long(digitizer.nbins)*szf, szf});
        {
            py::gil_scoped_release _;
            size_t k = 0u;
            for(auto i: data)
            {
                auto tmp = digitizer.compute(i.first, i.second);
                auto arr = self.compute(tmp);
                std::copy(arr.begin(), arr.end(), out.mutable_data()+k);
                k += digitizer.nbins;
            }
        }
        return out;
    }

    py::object _agg(ProjectionAggregator const & self,
                    Digitizer            const & project,
                    ndarray<float>               pydata)
    {
        size_t size = pydata.shape(0);
        if(size == 0)
            return ndarray<float>();
        if(size == 1)
            return pydata.attr("__getitem__")(0);

        std::vector<float const *> data;
        for(size_t i = 0u, ie = pydata.shape(0), sz = pydata.shape(1); i < ie; ++i)
            data.push_back(pydata.data()+sz*i);
        
        return toarray(pydata.shape(1), [&](){ return self.compute(project, data); });
    }

    py::object _all(py::object              cls,
                    BeadProjection const & self,
                    float                   prec,
                    ndarray<float>  const & pydata,
                    ndarray<int>    const & pyfirst,
                    ndarray<int>    const & pylast)
    {
        auto data = _cycles(pydata, pyfirst, pylast);
        auto arr  = DPX_GIL_SCOPED(self.compute(prec, data));
        return cls(toarray(arr.histogram), toarray(arr.bias),
                   arr.minvalue, arr.binwidth, toarray(arr.peaks));
    }

    py::object _align(CycleAlignment       const & self,
                      Digitizer            const & digit,
                      ProjectionAggregator const & agg,
                      ndarray<float>       const & pydata)
    {
        size_t size = pydata.shape(0);
        if(size == 0)
            return py::none();
        if(size == 1)
            return py::none();

        std::vector<float const *> data;
        for(size_t i = 0u, ie = pydata.shape(0), sz = pydata.shape(1); i < ie; ++i)
            data.push_back(pydata.data()+sz*i);

        auto out = DPX_GIL_SCOPED(self.compute(digit, agg, data));
        return py::make_tuple(toarray(out.first), toarray(out.second));
    }

    py::object _eventscompute(EventExtractor  const & self,
                              float                   prec,
                              py::object              proj,
                              ndarray<float>  const & pydata,
                              ndarray<int>    const & pyfirst,
                              ndarray<int>    const & pylast)
    {
        auto data  = _cycles(pydata, pyfirst, pylast);
        auto peaks = proj.attr("peaks").cast<ndarray<float>>();
        auto bias  = proj.attr("bias").cast<ndarray<float>>();
        auto arr   = DPX_GIL_SCOPED(self.compute(prec, peaks.size(),
                    peaks.data(), bias.data(), data));
        size_t szf = sizeof(int);
        if(arr.size() == 0)
            return py::none();

        std::vector<size_t> shape   = {arr.size(), arr.front().size(), 2u};
        std::vector<size_t> strides = {arr.front().size()*2u*szf, 2u*szf, szf};
        ndarray<int> out(shape, strides);
        auto ptr = out.mutable_data();
        for(size_t icyc = 0u, ecyc = arr.size(); icyc < ecyc; ++icyc)
            for(size_t ipks = 0u, epks = arr.front().size(); ipks < epks; ++ipks, ++ptr)
            {
                ptr[0]     = (int) arr[icyc][ipks].first;
                (++ptr)[0] = (int) arr[icyc][ipks].second;
            }
        return std::move(out);
    }

    py::object _eventsextract(EventExtractor  const & self,
                              float                   prec,
                              py::object              proj,
                              ndarray<float>  const & pydata,
                              ndarray<int>    const & pyfirst,
                              ndarray<int>    const & pylast)
    {
        auto dist  = self.distance * prec;
        auto data  = _cycles(pydata, pyfirst, pylast);
        auto bias  = proj.attr("bias").cast<ndarray<float>>();
        auto peaks = proj.attr("peaks").cast<ndarray<float>>();
        auto arr   = DPX_GIL_SCOPED(self.compute(prec, peaks.size(),
                            peaks.data(), bias.data(), data));

        py::list lst;
        for(size_t icyc = 0u, ecyc = arr.size(); icyc < ecyc; ++icyc)
        {
            py::list  cur;
            lst.append(cur);

            for(size_t ipks = 0u, epks = arr[icyc].size(); ipks < epks; ++ipks)
            {
                auto rng  = arr[icyc][ipks];
                auto minv = peaks.data()[ipks]+bias.data()[icyc]-dist;
                auto maxv = peaks.data()[ipks]+bias.data()[icyc]+dist;
                auto intv = toarray(rng.second-rng.first, data[icyc].second+rng.first);
                for(auto ptr = intv.mutable_data(), eptr = ptr+intv.size(); ptr != eptr; ++ptr)
                    if(ptr[0] < minv || ptr[0] >= maxv)
                        ptr[0]  = std::numeric_limits<float>::quiet_NaN();
                cur.append(py::make_tuple(rng.first, intv));
            }
        }
        return std::move(lst);
    }

    void pymodule(py::module & mod)
    {
        using namespace py::literals;
        {
            auto doc = R"_(Compute digitization of a cycle.)_";
            DPX_WRAP(Digitizer, (oversampling)(precision)(minedge)(maxedge)(nbins));
            cls.def("binwidth", &Digitizer::binwidth,
                    "oversampled"_a = false, R"_(Width of an (oversampled) bin)_");
            cls.def("compute",
                    [](Digitizer const & self, ndarray<float> data)
                    { 
                        ndarray<int> out(data.size());
                        auto tmp = self.compute(data.size(), data.data()).digits;
                        std::copy(tmp.begin(), tmp.end(), out.mutable_data());
                        return out;
                    }, 
                    "data"_a);
        }

        {
            auto doc = R"_(Compute digitization configuration.)_";
            DPX_WRAP(CyclesDigitization, (oversampling)(precision)(minv)(maxv)(overshoot));
            cls.def("compute", &_digit,
                    "precision"_a, "data"_a, "measurestart"_a, "measureend"_a);
                    
        }

#       define _DPX_PF_ENUM(_,CLS,X)  .value(BOOST_PP_STRINGIZE(X), CycleProjection::CLS::X)
#       define DPX_PF_ENUM(CLS, SEQ)                        \
            py::enum_<CycleProjection::CLS>(mod, "CycleProjection"#CLS)\
                BOOST_PP_SEQ_FOR_EACH(_DPX_PF_ENUM,CLS,SEQ);

        DPX_PF_ENUM(DzPattern,     (symmetric1))
        DPX_PF_ENUM(WeightPattern, (ones)(inv))

        {
            auto doc = R"_(Projects cycles onto a histogram with normalized peak heights.

Normalized peak heights means that a hybridization duration don't affect
the peak heights too much.)_";
            DPX_WRAP(CycleProjection,
                     (dzratio)(dzpattern)           \
                     (countratio)(countthreshold)   \
                     (weightpattern)                \
                     (tsmoothingratio)(tsmoothinglen));
            cls.def("compute", &_call, "digitizer"_a, "data"_a);
            cls.def("compute", &_callall,
                    "digitizer"_a, "data"_a, "measurestart"_a, "measureend"_a);
        }

        {
            auto doc = R"_(Aggregates projected cycles.)_";
            DPX_WRAP(ProjectionAggregator,
                     (cycleminvalue)(cyclemincount) \
                     (zsmoothingratio)(countsmoothingratio)(smoothinglen));
            cls.def("compute", &_agg, "precision"_a, "data"_a);
        }

        {
            auto doc = R"_(Aligns cycles by correlating to the overall projection.)_";
            DPX_WRAP(CycleAlignment, (halfwindow)(repeats));
            cls.def("compute", &_align, "digitizer"_a, "projector"_a, "histograms"_a);
        }

        auto beadproj = dpx::pyinterface::make_namedtuple(mod, "BeadProjectionData",
                "histogram", ndarray<float>(0),
                "bias",      ndarray<float>(0),
                "minvalue",  0.f,
                "binsize",   0.f,
                "peaks",     ndarray<float>(0)
                );

        {
            auto doc = R"_(Projects all cycles onto a histogram with normalized peak heights.

Normalized peak heights means that a hybridization duration don't affect
the peak heights too much.)_";
            DPX_WRAP(BeadProjection, (digitize)(project)(aggregate)(align)(find));
            cls.def("compute",
                    [beadproj](BeadProjection const & self,
                       float a,
                       ndarray<float> b,
                       ndarray<int> c,
                       ndarray<int> d
                    ) { return _all(beadproj, self, a, b, c, d); },
                    "precision"_a, "data"_a, "measurestart"_a, "measureend"_a);
        }

        {
            auto doc = R"_(Extracts events from the data.

Start & stop positions are as follows:

* At least *mincount* frames are within ± `distance`∙σ[HF] of the peak position.
* The density of such frames is above `density`.
)_";
                 
            DPX_WRAP(EventExtractor, (mincount)(density)(distance));
            cls.def("compute", _eventscompute,
                    "precision"_a, "projection"_a, "data"_a,
                    "measurestart"_a, "measureend"_a,
                    "Compute event start and end positions");
            cls.def("events", _eventsextract,
                    "precision"_a, "projection"_a, "data"_a,
                    "measurestart"_a, "measureend"_a,
                    "Create events from data");
        }
    }
}}

namespace peakfinding {
    namespace
    {
        ndarray<float> _find(HistogramPeakFinder const & self,
                             float                       prec,
                             py::object                  data)
        {
            auto hist = data.attr("histogram").cast<ndarray<float>>();
            auto minw = data.attr("minvalue").cast<float>();
            auto bw   = data.attr("binsize").cast<float>();
            std::vector<float> out = DPX_GIL_SCOPED(self.compute(prec, minw, bw, hist.size(), hist.data()));
            return toarray(out);
        }
    }
    namespace emutils { void pymodule(py::module &); }

    void pymodule(py::module & mod)
    {
        {
            using namespace py::literals;
            auto doc = R"_(Find peaks in a histogram)_";
            DPX_WRAP(HistogramPeakFinder, (peakwidth)(threshold));
            cls.def("compute", _find, "precision"_a, "histogram"_a);
        }
        projection::pymodule(mod);
        emutils::pymodule(mod);
    }
}
