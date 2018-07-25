#include <limits>
#include <boost/accumulators/statistics/mean.hpp>
#include <boost/accumulators/statistics/min.hpp>
#include <boost/accumulators/statistics/max.hpp>
#include <boost/math/distributions/chi_squared.hpp>
#include "signalfilter/accumulators.hpp"
#include "eventdetection/splitting.h"

namespace eventdetection {  namespace splitting {

namespace
{
    constexpr std::size_t operator "" _s (unsigned long long int x) { return x; }

    template <typename T1, typename T2, typename T3>
    void _apply(size_t i1, size_t sz, T1 && isgood, T2 && fcngood, T3 && fcnbad)
    {
        while(i1 < sz && !isgood(i1))
            ++i1;
        if(i1)
            fcnbad(0_s, i1);

        while(i1 < sz)
        {
            auto i2 = i1+1;
            while(i2 < sz && isgood(i2))
                ++i2;

            fcngood(i1, i2);

            i1 = i2;
            while(i1 < sz && !isgood(i1))
                ++i1;

            fcnbad(i2, i1);
        }

    }

    template <typename T1, typename T2>
    void _apply(size_t i1, size_t sz, T1 && isgood, T2 && fcngood)
    { _apply(i1, sz, std::move(isgood), std::move(fcngood), [](size_t, size_t){}); }

    template <typename T>
    grade_t _sum(size_t wlen, T const & data)
    {
        auto const sz = data.size();
        grade_t tmp(data.size()+wlen-1_s);

        for(size_t i = 0_s; i < wlen; ++i)
            tmp[std::slice(i, sz, 1_s)] += data;

        tmp *= 1.0f/wlen;
        for(size_t i = 0_s; i < wlen-1; ++i)
        {
            tmp[i]             *= wlen/float(i+1);
            tmp[sz+wlen-2_s-i] *= wlen/float(i+1);
        }
        return tmp;
    }

    std::tuple<grade_t, std::valarray<size_t>> _removenans(data_t const & nandata)
    {
        auto ptr = std::get<0>(nandata);
        auto sz  = std::get<1>(nandata);
        std::valarray<size_t> nans(sz);
        grade_t               data(sz);
        auto itd = std::begin(data);
        auto itn = std::begin(nans);
        _apply( 0_s, data.size(),
                [ptr]      (size_t i)             { return std::isfinite(ptr[i]); },
                [&itd, ptr](size_t i1, size_t i2)
                { std::copy(ptr+i1, ptr+i2, itd); itd += i2-i1; },
                [&itn]     (size_t i1, size_t i2)
                { for(; i1 < i2; ++i1, ++itn) *itn = i1; });

        if(itn == std::begin(nans))
            return {data, {}};
        return { data[std::slice(0_s, itd - std::begin(data), 1_s)],
                 nans[std::slice(0_s, itn - std::begin(nans), 1_s)]};
    }

    ints_t _tointervals(std::valarray<size_t> const & nans, grade_t const & grade)
    {
        ints_t intervals;
        _apply( 0_s, grade.size(),
                [&grade]     (size_t i)             { return grade[i] < 1.0f; },
                [&intervals] (size_t i1, size_t i2) { intervals.push_back({i1, i2}); });

        if(nans.size() == 0)
            return intervals;

        auto first = std::begin(nans), itr = std::begin(nans), last = std::end(nans);
        for(auto & i: intervals)
        {
            if(itr != last)
                itr       = std::upper_bound(itr, last, i.first);
            i.first  += itr - first;

            if(itr != last)
                itr       = std::upper_bound(itr, last, i.second);
            i.second += itr - first;
        }
        return intervals;
    }

    template <typename T>
    ints_t _extend(T const self, float precision, data_t const & info, ints_t && intervals)
    {
        namespace ba    = boost::accumulators;
        namespace bat   = boost::accumulators::tag;
        using     acc_t = ba::accumulator_set<float,
                                              ba::stats<bat::min, bat::max, bat::mean>>;

        auto const wlen = self.extensionwindow;
        auto const data = std::get<0>(info);
        auto const sz   = std::get<1>(info);

        precision      *= self.extensionratio;
        for(auto & i: intervals)
        {
            acc_t acc;
            for(auto j = i.first, e = i.second; j < e; ++j)
                if(std::isfinite(data[j]))
                    acc(data[j]);

            auto mean = ba::extract_result<bat::mean>(acc);
            auto rmin = std::min(ba::extract_result<bat::min>(acc), mean-precision);
            auto rmax = std::max(ba::extract_result<bat::max>(acc), mean+precision);

            for(auto j = i.first > wlen ? i.first-wlen : 0_s, e = i.first; j < e; ++j)
                if(std::isfinite(data[j]) && rmin <= data[j] && data[j] <= rmax)
                {
                    i.first = j;
                    break;
                }

            for(int j = int(std::min(i.second+wlen-1_s, sz)), e = int(i.second); j > e; --j)
                if(std::isfinite(data[j]) && rmin <= data[j] && data[j] <= rmax)
                {
                    i.second = j;
                    break;
                }
        }
        return intervals;
    }

    template <typename T>
    ints_t _compute(T const & self, float prec, data_t const & nandata)
    {
        auto   info = _removenans(nandata);
        auto & good = std::get<0>(info);
        auto & nans = std::get<1>(info);
        if(good.size() == 0)
            return {};
        if(prec <= 0.0f)
            prec = signalfilter::stats::hfsigma(good.size(), &good[0]);

        self.grade(prec, good);
        return _extend(self, prec, nandata, _tointervals(nans, good));
    }

    void _chi2grade(size_t wlen, float rho, grade_t & data)
    {
        wlen            = (wlen/2_s)*2_s+1_s;
        auto const hlen = wlen/2_s;
        auto const sz   = data.size();

        auto cpy        = data;
        auto mean(_sum(wlen, cpy));

        grade_t tmp(wlen);
        auto    var     = [&cpy, &tmp](size_t i1, float m)
                            {
                                tmp  = -m;
                                tmp += cpy[std::slice(i1, tmp.size(), 1_s)];
                                tmp *= tmp;
                                return tmp.sum()/tmp.size();
                            };

        for(auto i = hlen, e = sz-hlen; i < e; ++i)
            data[i] = var(i-hlen, mean[i+hlen]);

        for(auto i = 0_s; i < hlen; ++i)
        {
            tmp.resize(i+hlen+1_s);
            data[i]        = var(0_s,           mean[i+hlen]);
            data[sz-1_s-i] = var(sz-hlen-1_s-i, mean[sz+hlen-1_s-i]);
        }

        data  = std::sqrt(data);
        data *= 1.0f/rho;
    }

}

float DerivateSplitDetector::threshold(float precision, grade_t const & data) const
{
    grade_t tmp  = data;
    auto    perc = signalfilter::stats::percentile(&tmp[0], &tmp[0]+tmp.size(),
                                                   this->percentile);
    return perc+this->distance*precision;
}

void DerivateSplitDetector::grade(float precision, grade_t & data) const
{
    auto wlen = this->gradewindow;
    auto tmp(_sum(wlen, data));
    auto sz   = data.size();
    auto tsz  = tmp.size();
    auto sl   = [&sz](size_t i) { return std::slice(i, sz-1_s, 1_s); };

    data[sl(1_s)]  = tmp[sl(0_s)];
    data[0_s]      = tmp[0_s];
    data[sl(0_s)] -= tmp[sl(wlen)];
    data[sz-1_s]  -= tmp[tsz-1_s];
    data          *= 1./this->threshold(precision, data);
}

ints_t DerivateSplitDetector::compute(float precision, data_t data) const
{ return _compute(*this, precision, data); }

float ChiSquareSplitDetector::threshold(float prec) const
{
    namespace bm = boost::math;
    auto x = bm::quantile(bm::complement(bm::chi_squared(this->gradewindow-1),
                                         this->confidence));
    return prec*x/this->gradewindow;
}

void ChiSquareSplitDetector::grade(float precision, grade_t & data) const
{
    auto const wlen = (this->gradewindow/2)*2+1;
    auto const rho  = this->threshold(precision);
    _chi2grade(wlen, rho, data);
}

ints_t ChiSquareSplitDetector::compute(float precision, data_t data) const
{ return _compute(*this, precision, data); }

void MultiGradeSplitDetector::grade(float precision, grade_t & grade) const
{
    auto data(grade);
    this->derivate.grade(precision, grade);

    auto const sz   = grade.size();
    auto const hmin = this->minpatchwindow/2_s;
    auto const wmin = (this->minpatchwindow/2_s)*2_s+1_s;
    auto const wlen = (this->chisquare.gradewindow/2_s)*2_s+1_s;
    auto const hlen = this->chisquare.gradewindow/2_s;
    auto const rho  = this->chisquare.threshold(precision);

    auto patch = [&](bool found, size_t first, size_t last)
        {
            if(!found)
                return;

            last        = std::min(sz, last);
            grade_t tmp = data[std::slice(first, last, 1_s)];
            _chi2grade(wlen, rho, tmp);
            _apply( first+hlen, last-hlen,
                    [&grade](size_t i) { return grade[i] >= 1.0f; },
                    [&grade, &tmp, first, hmin, wmin](size_t i1, size_t i2) 
                    { 
                        if(i2-i1 >= wmin)
                        {
                            std::slice gs(i1+hmin,       i2-i1-2_s*hmin, 1_s);
                            std::slice ts(i1-first+hmin, i2-i1-2_s*hmin, 1_s);
                            grade[gs] = tmp[ts];
                        }
                    });
        };

    bool found = false;
    auto first = 0_s, last = 0_s;
    _apply( 0_s, sz,
            [&grade](size_t i) { return grade[i] >= 1.0f; },
            [&first, &last, &found, &patch, sz, hlen, wmin](size_t i1, size_t i2)
            {
                auto cur = i2-i1 >= wmin;
                if(!(found && cur && last+hlen > i1))
                {
                    patch(found, first, last);
                    found = cur;
                    first = i1 < hlen ? 0_s : i1-hlen;
                }
                last = i2 + hlen;
            });
    patch(found, first, last);
}

ints_t MultiGradeSplitDetector::compute(float precision, data_t data) const
{ return _compute(*this, precision, data); }

ints_t IntervalExtensionAroundRange::compute(float     precision,
                                              data_t    data,
                                              ints_t && intervals) const
{ return _extend(*this, precision, data, std::move(intervals)); }
}}