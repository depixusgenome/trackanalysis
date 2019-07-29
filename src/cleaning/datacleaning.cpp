#include <vector>
#include <limits>
#include "cleaning/datacleaning.h"
#include "signalfilter/accumulators.hpp"

namespace cleaning
{
    template <typename T>
    void ConstantValuesSuppressor<T>::apply(size_t sz, T * data) const
    {
        size_t i = 1, j = 0;
        auto check = [&]()
            {
                if(j+mindeltarange <= i)
                    for(size_t k = j+1; k < i; ++k)
                        data[k] = std::numeric_limits<T>::quiet_NaN();
            };

        for(; i < sz; ++i)
        {
            if(std::isnan(data[i]) || std::abs(data[i]-data[j]) < mindeltavalue)
                continue;

            check();
            j = i;
        }

        check();
    }
    template struct ConstantValuesSuppressor<float>;
    template struct ConstantValuesSuppressor<double>;

    template <typename T>
    void DerivateSuppressor<T>::apply(size_t sz, T * data, bool doclip, double azero) const
    {
        int     e    = int(sz);
        T       zero = T(azero);
        if(!doclip)
        {
            int i1 = 0;
            for(; i1 < e && std::isnan(data[i1]); ++i1)
                ;

            if(i1 < e)
            {

                T d0 = data[i1];
                T d1 = data[i1];
                for(int i2  = i1+1; i2 < e; ++i2)
                {
                    if(std::isnan(data[i2]))
                        continue;

                    if(std::abs(d1-zero) > maxabsvalue || std::abs(d1-.5*(d0+data[i2])) > maxderivate)
                        data[i1] = NAN;

                    d0 = d1;
                    d1 = data[i2];
                    i1 = i2;
                }

                if(std::abs(d1-zero) > maxabsvalue || std::abs(.5*(d1-d0)) < maxderivate)
                    data[i1] = NAN;
            }
        } else
        {
            T const high = zero+maxabsvalue;
            T const low  = zero-maxabsvalue;
            for(int i = 0; i < e; ++i)
            {
                if(std::isnan(data[i]))
                    continue;
                if(data[i] > maxabsvalue + zero)
                    data[i] = high;
                else if(data[i] < zero - maxabsvalue)
                    data[i] = low;
            }
        }
    }
    template struct DerivateSuppressor<float>;
    template struct DerivateSuppressor<double>;

    void LocalNaNPopulation::apply(size_t sz, float * data) const
    {
        if(window*2+1 >= sz)
            return;

        std::vector<int> tmp(sz);
        signalfilter::stats::nanthreshold(window, int((ratio*window)/100+1), sz,
                                          data, tmp.data());

        for(size_t i = window, e = sz-window-1; i < e; ++i)
            if(tmp[i-window] && tmp[i+1])
                data[i] = std::numeric_limits<float>::quiet_NaN();
    }

    void NaNDerivateIslands::apply(size_t sz, float * data) const
    {
        if(riverwidth > sz)
            return;

        std::vector<int> tmp(sz);
        signalfilter::stats::nanthreshold(riverwidth, int(riverwidth), sz, data, tmp.data());
        size_t nm1 = 0;
        bool first = true;
        for(size_t i = 0; i < riverwidth+1; ++i)
            if(std::isfinite(data[riverwidth-i]))
            {
                nm1   = riverwidth-1;
                first = false;
                break;
            }

        for(size_t i = riverwidth+1, e = sz-riverwidth; i < e; ++i)
        {
            if(!std::isfinite(data[i]))
                continue;
            if(tmp[i-riverwidth])
                for(size_t j = std::min(sz-1, i+islandwidth+1); j > i; --j)
                {
                    if(!(tmp[j] && std::isfinite(data[j-1])))
                        continue;

                    size_t count = size_t(0);
                    size_t n     = i;
                    if(first)
                    {
                        nm1 = i;
                        while(nm1 < j-1 && !std::isfinite(data[nm1]))
                            ++nm1;
                        n   = nm1+1;
                    }

                    while(n < j-1 && !std::isfinite(data[n]))
                        ++n;

                    size_t good  = size_t(0);
                    for(size_t np1 = n+1; n < j-1 && np1 < sz; ++np1)
                    {
                        if(!std::isfinite(data[np1]))
                            continue;

                        ++good;
                        if(std::abs((data[nm1]+data[np1])*.5f-data[n]) > maxderivate)
                            ++count;
                        nm1 = n;
                        n   = np1;
                    }

                    if(good > 0 && (count*100 < ratio*good))
                        continue;

                    for(size_t k = i; k < j; ++k)
                        data[k] = std::numeric_limits<float>::quiet_NaN();
                    break;
                }
            nm1 = i;
        }
    }

    void AberrantValuesRule::apply(size_t sz, float * data, bool clip) const
    {
        using namespace signalfilter::stats;
        acc_t<bat::median> med;
        for(size_t i = 0; i < sz; ++i)
            if(std::isfinite(data[i]))
                med(data[i]);

        if(!clip)
        {
            // remove values outside an absolute range and derivatives outside an absolute range
            derivative.apply(sz, data, false, compute(med));
            // remove stretches of constant values
            constants.apply(sz, data);
        }
        // remove NaN features
        localnans.apply(sz, data);
        islands.apply(sz, data);
    }

    DataOutput::DataOutput(size_t ncycles)
        : values(ncycles, std::numeric_limits<float>::quiet_NaN()),
          minv  (),
          maxv  ()
    {}

    namespace
    {
        template <typename T>
        bool _has(T);

        template <typename T>
        decltype(_has(&T::minv)) _testmin(T const & self, float val) { return val < self.minv; }

        template <typename T>
        constexpr bool _testmin(T const &, ...) { return false; }

        template <typename T>
        decltype(_has(&T::maxv)) _testmax(T const & self, float val) { return val > self.maxv; }

        template <typename T>
        constexpr bool _testmax(T const &, ...) { return false; }

        float _test(HFSigmaRule const &, size_t sz, float const *data)
        { return signalfilter::stats::nanhfsigma(sz, data); }

        float _test(PopulationRule const &, size_t sz, float const *data)
        {
            float cnt = 0.f;
            for(size_t i = 0; i < sz; ++i)
                if(std::isfinite(data[i]))
                    ++cnt;
            return sz == 0 ? 0.0f : cnt/sz*100.0f;
        }

        template <typename T>
        float _test_extent(T const & self, size_t sz, float const *data)
        {
            auto imax = int(self.maxpercentile*.01*sz);
            auto imin = int(self.minpercentile*.01*sz);
            if(imax == 100 && imin == 0)
            {
                auto maxv = std::max_element(data, data+sz);
                auto minv = std::min_element(data, data+sz);
                return float(maxv-minv);
            }

            std::vector<float> cpy(data, data+sz);
            auto dt   = cpy.data();
            auto maxv = signalfilter::stats::nanpercentile(dt, dt+sz, (float) self.maxpercentile);
            auto minv = signalfilter::stats::nanpercentile(dt, dt+sz, (float) self.minpercentile);
            return float(maxv-minv);
        }
        float _test(ExtentRule const & self, size_t sz, float const *data)
        {   return _test_extent(self, sz, data); }

        float _test(PingPongRule const & self, size_t sz, float const *data)
        {
            auto ext = _test_extent(self, sz, data);
            if(!std::isfinite(ext) || ext == 0.0f)
                return std::numeric_limits<float>::quiet_NaN();

            auto invext = 1.0f/ext;
            auto conv   = 0.0f;
            for(size_t i = 4; i < sz; ++i)
            {
                auto val = std::abs((data[i]-data[i-4])*(1.0f/12.0f)
                                     +(data[i-3]-data[i-1])*(2.0f/3.0f));
                if(std::isfinite(val) && val > self.mindifference)
                    conv += val*invext;
            }
            return conv;
        }

        float _test(PhaseJumpRule const &self, size_t sz, float const *data)
        {
            int num_jumps = 0;

            for (size_t i = 1; i < sz; ++i)
            {
                float diff = std::abs(data[i] - data[i - 1]);
                bool is_phase_jump = (self.phasejumpheight - self.delta) < diff &&
                                     diff < (self.phasejumpheight + self.delta);
                if (is_phase_jump)
                    num_jumps++;
            }
            return float(num_jumps);
        }

        template <typename T>
        DataOutput _apply(T const & self, DataInfo const & info)
        {
            DataOutput out(info.ncycles);
            for(size_t icyc = 0; icyc < info.ncycles; ++icyc)
            {
                auto value = _test(self,
                                   info.stop[icyc]-info.start[icyc],
                                   info.data+info.start[icyc]);
                out.values[icyc] = value;
                if(_testmin(self, value))
                    out.minv.push_back((int) icyc);
                if(_testmax(self, value))
                    out.maxv.push_back((int) icyc);
            }
            return out;
        }
    }
    
    DataOutput HFSigmaRule::apply(DataInfo info) const
    { return _apply(*this, info); }

    DataOutput PopulationRule::apply(DataInfo info) const
    { return _apply(*this, info); }

    DataOutput ExtentRule::apply(DataInfo info) const
    {  return _apply(*this, info); }

    DataOutput PingPongRule::apply(DataInfo info) const
    {  return _apply(*this, info); }

    DataOutput PhaseJumpRule::apply(DataInfo info) const
    {  return _apply(*this, info); }

    DataOutput SaturationRule::apply(DataInfo initial, DataInfo measures) const
    {
        DataOutput out(initial.ncycles);
        auto zeros = size_t(0);
        auto good  = size_t(0);
        for(auto icyc = size_t(0); icyc < initial.ncycles; ++icyc)
        {
            std::vector<float> tmp(measures.data+measures.stop[icyc]-satwindow,
                                   measures.data+measures.stop[icyc]);
            auto diffmed = signalfilter::stats::nanmedian(tmp);
            if(!std::isfinite(diffmed))
                continue;

            tmp.assign(initial.data+initial.start[icyc],
                       initial.data+initial.stop[icyc]);
            diffmed -= signalfilter::stats::nanmedian(tmp);
            
            out.values[icyc] = diffmed;
            if(std::isfinite(diffmed))
            {
                ++good;
                if(diffmed > maxdisttozero)
                    ++zeros;
            }

        }
        if(zeros*100 > good*maxv)
        {
            out.maxv.resize(initial.ncycles);
            for(auto i = size_t(0); i < initial.ncycles; ++i)
                out.maxv.at(i) = int(i);
        }
        return out;
    }
}
