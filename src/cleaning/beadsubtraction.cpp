#include <algorithm>
#include "cleaning/beadsubtraction.h"
#include "signalfilter/accumulators.hpp"

namespace cleaning { namespace beadsubtraction {

namespace {
    using signalfilter::stats::median;

    template <typename K>
    std::vector<float>
    _signal(std::vector<data_t> const & signals, size_t i1, size_t i2, K && fcn)
    {
        size_t len = 0;
        for(auto const & i: signals)
            len = std::max(len, std::get<1>(i));

        std::vector<data_t> good;
        std::vector<float>  offsets, wtable;

        good   .reserve(signals.size());
        offsets.reserve(signals.size());
        if(i1 < i2)
            for(auto const & i: signals)
            {
                wtable.resize(0);
                auto ptr(std::get<0>(i));
                auto sz (std::get<1>(i));
                for(auto i = std::min(i1, sz), e = std::min(i2, sz); i < e; ++i)
                    if(std::isfinite(ptr[i]))
                        wtable.push_back(ptr[i]);

                if(wtable.size())
                {
                    offsets.push_back(median(wtable));
                    good   .push_back(i);
                }
            }
        else
        {
            offsets = std::vector<float>(signals.size(), 0.0f);
            good    = signals;
        }

        if(offsets.size() == 0)
            return {};

        wtable = offsets;
        auto med(median(wtable));
        for(auto &i: offsets)
            i -= med;

        auto minlen = len;
        for(auto const & i: good)
            minlen = std::min(minlen, std::get<1>(i));

        std::vector<float> out(len, std::numeric_limits<float>::quiet_NaN());
        for(size_t i = 0u, e = offsets.size(); i < minlen; ++i)
        {
            wtable.resize(0);
            for(size_t j = 0; j < e; ++j)
            {
                auto val(std::get<0>(good.at(j))[i]);
                if(std::isfinite(val))
                    wtable.push_back(val-offsets.at(j));
            }
            if(wtable.size())
                out.at(i) = fcn(wtable);
        }

        for(size_t i = minlen, e = offsets.size(); i < len; ++i)
        {
            wtable.resize(0);
            for(size_t j = 0; j < e; ++j)
            {
                auto sz (std::get<1>(good.at(j)));
                if(sz <= i)
                    continue;

                auto val(std::get<0>(good.at(j))[i]);
                if(std::isfinite(val))
                    wtable.push_back(val-offsets.at(j));
            }
            if(wtable.size())
                out.at(i) = fcn(wtable);
        }
        return out;
    }
}

std::vector<float> mediansignal(std::vector<data_t> const & signals, size_t i1, size_t i2)
{ return _signal(signals, i1, i2, [](auto & x) { return signalfilter::stats::median(x); }); }

std::vector<float> meansignal(std::vector<data_t> const & signals, size_t i1, size_t i2)
{ 
    return _signal(signals, i1, i2,
                   [](auto & x) 
                   { return std::accumulate(x.begin(), x.end(), 0.0f)/x.size(); });
}

std::vector<float> stddevsignal(std::vector<data_t> const & signals, size_t i1, size_t i2)
{ 
    using namespace signalfilter::stats;
    return _signal(signals, i1, i2,
                   [](auto & x)  
                   {  return std::sqrt(compute<bat::variance>(x.size(), x.data())); });
}
}}
