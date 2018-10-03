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

    template <typename K>
    std::vector<float>
    _measure(data_t const & signals, size_t sz, int const * i1, int const * i2, K && meas)
    {
        int          len  = int(std::get<1>(signals));
        float const *data = std::get<0>(signals);
        std::vector<float> out(sz, std::numeric_limits<float>::quiet_NaN());
        for(size_t i = 0u; i < sz && i1[i] < len && i2[i] < len; ++i)
            out[i] = meas(data+i1[i], data+i2[i], 0.f);
        return out;
    }

    template <typename K1, typename K2>
    std::vector<float>
    _measure(std::vector<data_t> const & signals, size_t sz, int const * i1, int const * i2, K1 && meas,  K2 && agg)
    {
        auto len = std::numeric_limits<int>::max();
        for(auto const & i: signals)
            len = std::min(len, int(std::get<1>(i)));

        std::vector<float const *> data;
        for(auto const & j: signals)
            data.push_back(std::get<0>(j));
        auto e = data.size();

        std::vector<float> orig(e);
        for(size_t j = 0u; j < e; ++j)
            orig[j] = meas(data[j]+i1[0], data[j]+i2[0], 0.f);

        std::vector<float> out(sz, std::numeric_limits<float>::quiet_NaN());

        std::vector<float> tmp(orig);
        out[0] = 0.f;
        for(size_t i = 1u; i < sz && i1[i] < len && i2[i] < len; ++i)
        {
            for(size_t j = 0u; j < e; ++j)
                tmp[j] = meas(data[j]+i1[i], data[j]+i2[i], orig[i]);
            out[i] = agg(tmp);
        }
        return out;
    }

    template <typename K1, typename K2, typename K3>
    std::vector<float>
    _measure(std::vector<data_t> const & signals, size_t sz, int const * i1, int const * i2,
             K1 && meas,  K2 && zero, K3 && agg)
    {
        std::vector<std::vector<float>> data;
        for(auto const & i: signals)
        {
            data.push_back(_measure(i, sz, i1, i2, meas));

            auto tmp(data.back());
            auto z = zero(tmp);
            for(auto & x: data.back())
                x -= z;
        }

        std::vector<float> out(sz, std::numeric_limits<float>::quiet_NaN());
        std::vector<float> tmp(data.size());
        for(size_t i = 0u, e = data.size(); i < sz; ++i)
        {
            for(size_t j = 0u; j < e; ++j)
                tmp[j] = data[j][i];
            out[i] = agg(tmp);
        }
        return out;
    }


    float _median(float const * x1, float const * x2, float delta)
    { 
        std::vector<float> tmp(x1, x2);
        return signalfilter::stats::nanmedian(tmp)-delta; 
    }

    float _median2(std::vector<float> & data)
    {   return signalfilter::stats::median(data); }

    float _mean(float const * x1, float const * x2, float delta)
    { 
        double tot = 0.f;
        size_t cnt = 0;
        for(; x1 != x2; ++x1)
            if(std::isfinite(x1[0]))
            {
                tot += x1[0];
                ++cnt;
            }
        return tot/cnt - delta;
    }

    float _mean2(std::vector<float> const & data)
    { 
        double tot = 0.f;
        size_t cnt = 0;
        for(auto x: data)
            if(std::isfinite(x))
            {
                tot += x;
                ++cnt;
            }
        return tot/cnt;
    }
}

std::vector<float> phasebaseline(std::string txt,
                                 data_t signals,
                                 size_t cnt, int const * ix1,  int const * ix2)
{ return txt == "median" ? _measure(signals, cnt, ix1, ix2, _median) : 
         txt == "mean"   ? _measure(signals, cnt, ix1, ix2, _mean)   : 
         std::vector<float>();
}

#define DPX_PB_C2(X,Y)    \
     txt == #X "-" #Y ? _measure(signals, cnt, ix1, ix2, _##X, _##Y##2) : 
#define DPX_PB_C3(X,Y,Z)    \
     txt == #X "-" #Y "-" #Z  ? _measure(signals, cnt, ix1, ix2, _##X, _##Y##2, _##Z##2) : 
std::vector<float> phasebaseline(std::string txt,
                                 std::vector<data_t> const & signals,
                                 size_t cnt, int const * ix1,  int const * ix2)
{ 
    return DPX_PB_C2(median,median)        DPX_PB_C2(median,mean)
           DPX_PB_C2(mean,median)          DPX_PB_C2(mean,mean)
           DPX_PB_C3(median,median,median) DPX_PB_C3(median,mean,median)
           DPX_PB_C3(mean,median,median)   DPX_PB_C3(mean,mean,median)
           DPX_PB_C3(median,median,mean)   DPX_PB_C3(median,mean,mean)
           DPX_PB_C3(mean,median,mean)     DPX_PB_C3(mean,mean,mean)
           std::vector<float>();
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
