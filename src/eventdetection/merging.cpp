#include <list>
#include <tuple>
#include <cmath>
#include <algorithm>
#include "eventdetection/stattests.h"
#include "eventdetection/merging.h"

namespace eventdetection { namespace merging {

namespace {
    float get0(ints_t const & intr, size_t i) { return intr[i].first; }
    float get1(ints_t const & intr, size_t i) { return intr[i].second; }
}

namespace statsmerging
{
    template <typename T>
    struct Stats;

    template <>
    struct Stats<HeteroscedasticEventMerger>
    { using type = samples::normal::Input; };

    template <typename T>
    using EvMVal = std::tuple<typename Stats<T>::type, typename Stats<T>::type,
                               float, std::pair<size_t, size_t>>;
    template <typename T>
    using EvMList = std::list<EvMVal<T>>;

    template <typename T>
    using EvMIter = typename std::list<EvMVal<T>>::iterator;

    samples::normal::Input
    update(HeteroscedasticEventMerger const &,
           samples::normal::Input const & first,
           samples::normal::Input const & sec,
           samples::normal::Input const & third)
    {
        auto cnt   = first.count+sec.count+third.count;

        auto r1    = first.count/float(cnt);
        auto r2    = sec  .count/float(cnt);
        auto r3    = 1.0f - r1 - r2;
        auto mean  = r1*first.mean+r2*sec.mean+r3*third.mean;

        r1 = first.count == 0 ? 0 : (first.count-1)/float(cnt-1);
        r2 = sec  .count == 0 ? 0 : (sec  .count-1)/float(cnt-1);
        r3 = third.count == 0 ? 0 : (third.count-1)/float(cnt-1);
        auto sigma = std::sqrt(r1*first.sigma*first.sigma
                              +r2*sec.sigma*sec.sigma
                              +r3*third.sigma*third.sigma);
        return {cnt, mean, sigma};
    }

    float threshold(HeteroscedasticEventMerger const & self)
    { return samples::normal::heteroscedastic::threshold(self.confidence); }

    float pvalue(HeteroscedasticEventMerger const &,
                 samples::normal::Input     const & a,
                 samples::normal::Input     const & b)
    { return samples::normal::heteroscedastic::tothresholdvalue(a, b); }

    auto initstats(HeteroscedasticEventMerger const & self,
                   float const * data, size_t i1, size_t i2)
    {
        samples::normal::Input out = {0, 0.0f, 0.0f};
        for(size_t i = i1; i < i2; ++i)
            if(std::isfinite(data[i]))
            {
                out.count += 1;
                float rho = float(out.count-1)/out.count;
                out.mean  = rho * out.mean + data[i] * (1.0f-rho);
            }

        for(size_t i = i1, cnt = 0; i < i2; ++i)
            if(std::isfinite(data[i]))
            {
                cnt += 1;
                float rho   = float(cnt-1)/cnt;
                float delta = data[i]-out.mean;
                out.sigma = rho * out.sigma + delta*delta * (1.0f-rho);
            }

        if(out.count <= 1)
            out.sigma = self.minprecision;
        else
            out.sigma = std::max(self.minprecision,
                                 std::sqrt(out.sigma*(out.count/(out.count-1))));
        return out;
    };


    template <typename T>
    inline auto initstats(T const & self, float const *data, ints_t const & intervals)
    {
        auto first = initstats(self, data, get0(intervals, 0), get1(intervals, 0));
        EvMList<T>  statlist;
        for(size_t i = 1, e = intervals.size(); i < e; ++i) 
        {
            auto sec   = initstats(self, data, get1(intervals, i-1), get0(intervals, i));
            auto third = initstats(self, data, get0(intervals, i), get1(intervals, i));
            auto prob  = pvalue(self, first, third);

            statlist.push_back({first, sec, prob, intervals[i-1]});
            first = third;
        }
        statlist.push_back({first, typename Stats<T>::type(), 1.0f, intervals.back()});
        return statlist;
    }

    template <typename T>
    inline auto search(float thr, T & statlist)
    {
        auto best = statlist.begin();
        auto e    = statlist.end();
        for(; best != e && std::get<2>(*best) >= thr; ++best)
            ;

        if(best != e)
        {
            for(auto _ = best, cur = ++_; cur != e; ++cur)
                if(std::get<2>(*cur) <= std::get<2>(*best))
                    best = cur;
        }
        return best;
    }

    template <typename T>
    inline void update(T const & self, EvMList<T> & statlist, EvMIter<T> best)
    {
        auto rem   = best; ++rem;
        auto first = update(self,
                            std::get<0>(*best),
                            std::get<1>(*best),
                            std::get<0>(*rem));
        auto sec   = std::get<1>(*rem);
        auto after = rem;
        auto e     = statlist.end();
        if(after != e)
            ++after;

        *best = { first, sec,
                  after == e ? 1.0f : pvalue(self, first, std::get<0>(*after)),
                  {std::get<3>(*best).first, std::get<3>(*rem).second}};
        statlist.erase(rem);
    };

    template <typename T>
    void run(T const & self, float const *data, ints_t & intervals)
    {
        if(intervals.size() <= 1)
            return;

        auto thr = threshold(self);
        auto lst = initstats(self, data, intervals);
        for(auto i = search(thr, lst); i != lst.end(); i = search(thr, lst))
            update(self, lst, i);

        if(lst.size() < intervals.size())
        {
            intervals.resize(0);
            for(auto const & itm: lst)
                intervals.push_back(std::get<3>(itm));
        }
    }
}

void HeteroscedasticEventMerger::run(float const *data, ints_t & intervals) const
{ statsmerging::run(*this, data, intervals); }

namespace rangemerging
{
    using PopStats = std::tuple<float const*, float const *, float, float>;
    auto _isin(float a, float b, float c) { return a <= b && b <= c; }

    template <int I1, int I2, int I3>
    auto _isin(PopStats const & a, PopStats const & b) 
    { return _isin(std::get<I1>(a), std::get<I2>(b), std::get<I3>(a));}
    template <int I1, int I2>
    auto _delta(PopStats const & a) { return std::get<I1>(a)-std::get<I2>(a);  }

    PopStats popstats(float const *data, std::pair<size_t, size_t> const & inter)
    {
        auto first = data+inter.first;
        auto last  = data+inter.second;
        float minv = first[0], maxv = first[0];
        for(auto i = first+1; i != last; ++i)
            if(!std::isfinite(minv))
                minv = maxv = *i;
            else if(std::isfinite(*i))
            {
                minv = std::min(minv, *i);
                maxv = std::max(maxv, *i);
            }
        return { first, last, minv, maxv };
    }

    template <typename T, typename K>
    void run(T     const & self,
             float const * data,
             ints_t      & intervals,
             K             testpop)
    {
        std::vector<bool> rem(intervals.size(), true);
        auto              e(intervals.size());
        for(bool found = true; found;)
        {
            found        = false;
            size_t ileft = 0u;
            auto   left  = popstats(data, intervals[0]);
            for(size_t iright = 1u; iright < e; ++iright)
            {
                if(!rem[iright])
                    continue;

                auto right = popstats(data, intervals[iright]);
                if(testpop(self, data, left, right))
                {
                    rem[iright]      = false;
                    intervals[ileft] = {get0(intervals, ileft), get1(intervals, iright)};
                    left             = { std::get<0>(left), std::get<1>(right),
                                         std::min(std::get<2>(left), std::get<2>(right)),
                                         std::max(std::get<3>(left), std::get<3>(right)) };
                    found            = true;
                    break;
                }

                ileft = iright;
                left  = right;
            }
        }

        size_t j = 0;
        for(size_t i = 0; i < e; ++i)
            if(rem[i])
            {
                if(j != i)
                    intervals[j] = intervals[i];
                ++j;
            }
        intervals.resize(j);
    }
}

void PopulationMerger::run(float const * data, ints_t & intervals) const
{
    using namespace rangemerging;
    constexpr auto fcn  = [](PopulationMerger const & self,
                             float            const * data,
                             PopStats         const & left,
                             PopStats         const & right)
    {
        auto  check = [&self, data](PopStats const & one, PopStats const & other)
        {
            auto ngood = 0u, nboth = 0u;
            auto minv  = std::get<2>(one), maxv = std::get<3>(one);
            for(auto i = std::get<0>(other), e = std::get<1>(other); i != e; ++i)
                if(std::isfinite(*i))
                {
                    ++ngood;
                    if(_isin(minv, *i, maxv))
                        ++nboth;
                }

            auto nmin  = size_t(ngood * self.percentile*1e-2f+.5f);
            if(nmin == ngood && nmin > 1)
                nmin = ngood-2;
            return nmin <= nboth;
        };
        auto good  = (   _isin<2, 2, 3>(left,  right) || _isin<2, 3, 3>(left,  right)
                      || _isin<2, 2, 3>(right, left)  || _isin<2, 3, 3>(right, left));
        if(!good)
            return false;

        if(_delta<1, 0>(left) < _delta<1, 0>(right))
            return check(right, left)  || check(left,  right);
        return check(left,  right) || check(right, left);
    };

    rangemerging::run(*this, data, intervals, fcn); 
}

void ZRangeMerger::run(float const * data, ints_t & intervals) const
{
    using namespace rangemerging;
    constexpr auto fcn = [](ZRangeMerger const & self,
                            float        const *,
                            PopStats     const & left,
                            PopStats     const & right)
    {
        if(    (_delta<3,2>(left)  == 0.f && _isin<2, 2, 3>(right, left))
            || (_delta<3,2>(right) == 0.f && _isin<2, 2, 3>(left, right)))
            return true;
        auto rng = (std::min(std::get<3>(left), std::get<3>(right))
                    - std::max(std::get<2>(left), std::get<2>(right)))
                  /(self.percentile*1e-2f);
        return rng > _delta<3,2>(left) || rng > _delta<3,2>(right);
    };
    rangemerging::run(*this, data, intervals, fcn); 
}

void  MultiMerger::run(float const *data,  ints_t & intervals) const
{
    stats.run(data, intervals);
    pop.run(data, intervals);
    range.run(data, intervals);
}

void EventSelector::run(float const *data,  ints_t & intervals) const
{
    auto minl = 2*this->edgelength+this->minlength;
    if(minl == 0u)
        return;

    auto   elen = this->edgelength;
    size_t j    = 0u;
    for(size_t i = 0u, e = intervals.size(); i < e; ++i)
    {
        size_t i1 = intervals[i].first;
        size_t i2 = intervals[i].second;
        while(i1+minl <= i2 && !std::isfinite(data[i1]))
            ++i1;
        while(i1+minl <= i2 && !std::isfinite(data[i2]))
            --i2;
        if(i2 < minl+i1)
            continue;

        intervals[j] = {intervals[i].first+elen, intervals[i].second-elen};
        ++j;
    }
}
}}
