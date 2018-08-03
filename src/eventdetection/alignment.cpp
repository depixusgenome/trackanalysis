#include <vector>
#include <algorithm>
#include "signalfilter/accumulators.hpp"
#include "eventdetection/alignment.h"

namespace eventdetection { namespace alignment {
namespace {
    using namespace signalfilter::stats;

    template <typename T>
    info_t _ebincompute(size_t binsize, DataInfo const & data, T && fcn)
    {
        info_t out(data.ncycles);
        for(size_t i = 0; i < data.ncycles; ++i)
        {
            auto j    = size_t(data.first[i]), e = size_t(data.last[i]);
            auto ptr  = data.data+j;
            auto minv = std::numeric_limits<float>::max();
            for(; j+binsize < e; j += binsize, ptr += binsize)
                minv = fcn(minv, nanmedian(std::vector<float>(ptr, ptr+binsize)));
            if(j < e)
                minv = fcn(minv, nanmedian(std::vector<float>(ptr, data.data+e)));

            out[i] = -minv;
        }
        return out;
    }

    template <typename T>
    info_t _ecompute(DataInfo const & data, T && fcn)
    {
        info_t out(data.ncycles);
        auto   ptr(data.data);
        for(size_t i = 0; i < data.ncycles; ++i)
            out[i] = -fcn(ptr+data.first[i], ptr+data.last[i]);
        return out;
    }
}

info_t ExtremumAlignment::compute(DataInfo const && data) const
{
    info_t out;
    if(mode == ExtremumAlignment::median)
        out = _ecompute(data,
                        [](float const * a, float const *b)
                        { return signalfilter::stats::nanmedian(a, b); });
    else if(binsize >= 2)
    {
        if(mode == ExtremumAlignment::min)
            out = _ebincompute(binsize, data, [](float a, float b) { return a < b ? a : b; });
        else
            out = _ebincompute(binsize, data, [](float a, float b) { return a < b ? b : a; });
    } else if(mode == ExtremumAlignment::min)
        out = _ecompute(data,
                        [](float const * a, float const *b)
                        { return std::min_element(a, b)[0]; });
    else
        out = _ecompute(data,
                        [](float const * a, float const *b)
                        { return std::max_element(a, b)[0]; });
    return out;
}

info_t PhaseEdgeAlignment::compute(DataInfo const && data) const
{
    auto ptr  (data.data);
    auto first(data.first), last (data.last);
    int  sz   (window);

    info_t out(data.ncycles);
    if(mode == PhaseEdgeAlignment::left)
        for(size_t i = 0; i < data.ncycles; ++i)
        {
            std::vector<float> tmp(ptr+first[i], ptr+std::min(first[i]+sz, last[i]));
            out[i] = -signalfilter::stats::nanpercentile(tmp.data(),
                                                         tmp.data()+tmp.size(),
                                                         percentile);
        }
    else
        for(size_t i = 0; i < data.ncycles; ++i)
        {
            std::vector<float> tmp(ptr+std::max(first[i], last[i]-sz), ptr+last[i]);
            out[i] = -signalfilter::stats::nanpercentile(tmp.data(),
                                                         tmp.data()+tmp.size(),
                                                         percentile);
        }
    return out;
}

void translate(DataInfo const && data, bool del, float * ptr)
{
    if(data.ncycles == 0 || data.size == 0)
        return;

    auto delta(data.data);
    auto apply = [&](float tmp, size_t r1, size_t r2)
                  {
                      if(std::isfinite(tmp))
                          for(size_t j = r1; j < r2; ++j)
                              ptr[j] += tmp;
                      else if(del)
                          std::fill(ptr+r1, ptr+r2, std::numeric_limits<float>::quiet_NaN());
                  };
    for(size_t i = 0u, e = data.ncycles-1; i < e; ++i)
        apply(delta[i], data.first[i], data.first[i+1]);
    apply(delta[data.ncycles-1], data.first[data.ncycles-1], data.size);
}

void medianthreshold(DataInfo const && data, float minv, float * bias)
{
    using signalfilter::stats::nanmedian;
    auto ptr(data.data);

    std::vector<float> values;
    for(size_t i = 0u, e = data.ncycles; i < e; ++i)
        values.push_back(nanmedian(std::vector<float>(ptr+data.first[i], ptr+data.last[i]))
                         +bias[i]);

    auto med = nanmedian(std::vector<float>(values))-minv;
    if(!std::isfinite(med))
        return;


    for(size_t i = 0u, e = data.ncycles; i < e; ++i)
        if(values[i] < med)
            bias[i] = std::numeric_limits<float>::quiet_NaN();
}
}}
