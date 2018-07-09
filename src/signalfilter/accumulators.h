#pragma once
#include <boost/accumulators/accumulators.hpp>
#include <boost/accumulators/statistics/stats.hpp>
#include <valarray>

namespace boost { namespace accumulators { namespace tag {
    struct mediandeviation;
    struct rolling_min;
    struct rolling_argmin;
    struct rolling_max;
    struct rolling_argmax;
    struct exact_median;
    struct approx_median;
}}}

namespace signalfilter { namespace stats
{
    namespace ba  = boost::accumulators;
    namespace bat = boost::accumulators::tag;

    template <typename T>
    typename T::value_type median(T & items);

    template <typename T>
    auto median(T begin, T end);

    template <typename ... T>
    struct acc_t: public ba::accumulator_set<double, ba::stats<T...>>
    {
        using self_t = ba::accumulator_set<double, ba::stats<T...>>;
        acc_t()                      = default;
        acc_t(acc_t<T...> const &)   = default;
        acc_t(acc_t<T...>       &&)  = default;
        acc_t<T...> & operator = (acc_t<T...>       &&)  = default;

        template <typename C>
        explicit acc_t(C const & p);

        template <typename C>
        explicit acc_t(size_t sz, C const * p);

        template <typename Args, typename C>
        explicit acc_t(Args && args, size_t sz, C const * p);
    };

    using mean_t  = acc_t<bat::count, bat::mean>;
    using rm_t    = acc_t<bat::rolling_mean>;

    template <typename ... T>
    struct wacc_t: public ba::accumulator_set<double, ba::stats<T...>, double>
    {
        using self_t = ba::accumulator_set<double, ba::stats<T...>, double>;

        wacc_t()                       = default;
        wacc_t(wacc_t<T...> const &)   = default;
        wacc_t(wacc_t<T...>       &&)  = default;
        wacc_t<T...> & operator = (wacc_t<T...> &&) = default;

        template <typename C0, typename C1>
        explicit wacc_t     (C0 const & p, C1 const & w);

        template <typename C0, typename C1, typename C2>
        explicit wacc_t     (C0 const & p, C1 const & w, C2 const & cv);

        template <typename T0, typename T1>
        explicit wacc_t     (size_t sz, T0 p, T1 w);

        template <typename Args, typename T0, typename T1>
        explicit wacc_t     (Args && args, size_t sz, T0 p, T1 w);

        template <typename T0, typename T1, typename T2>
        explicit wacc_t     (size_t sz, T0 p, T1 w, T2 cv);

        template <typename Args, typename T0, typename T1, typename T2>
        explicit wacc_t     (Args && args, size_t sz, T0 p, T1 w, T2 cv);
    };

    template <typename ... T>
    struct RARolling : public wacc_t<T...>
    {
        constexpr static bool const forward  = true;
        constexpr static bool const backward = false;

        RARolling()                         = delete;
        RARolling(RARolling<T...> const &)  = default;
        RARolling(RARolling<T...>      &&)  = default;
        RARolling(size_t ws, bool dir = forward);

        template <typename P>
        RARolling(size_t ws, P const & ptr, bool dir = true);

        template <typename P, typename W>
        RARolling(size_t ws, P const & ptr, W const & wgt, bool dir = true);

        void setup(size_t ws, bool dir);

        template <typename P>
        void unsafe(P const * ptr);

        template <typename P, typename W>
        void unsafe(P const * ptr, W const * wgt);

        template <typename P>
        void operator() (P const * ptr);

        template <typename P, typename W>
        void operator() (P const * ptr, W const * wgt);

        private:
            void _do(double v, double w);

            int  _dir  = 1;
            int  _ws   = 1;
            int  _burn = 0;
    };

    template <typename ... T>
    struct Rolling : public wacc_t<T...>
    {
        Rolling()                       = delete;
        Rolling(Rolling<T...> const &)  = default;
        Rolling(Rolling<T...>      &&)  = default;
        Rolling(size_t ws) : _vals(ws), _wgts(ws) {}

        void setup(size_t ws);

        void operator() (double val, double wgt = 1.);

        private:
            void _do(double v, double w);

            std::valarray<double>   _vals;
            std::valarray<double>   _wgts;
            size_t                  _ind  = 0;
            size_t                  _burn = 0;
    };

    template <typename T, typename C>
    auto compute(size_t sz, C const * elems);

    template <typename T, typename C>
    auto compute(C const & elems)
    ->  typename
        std::enable_if<!std::is_arithmetic<C>::value,
                       decltype(ba::extract_result<T>(acc_t<T>(elems)))
                      >::type;

    template <typename T>
    inline auto compute(acc_t<T> const & x);

    template <typename T>
    T hfsigma(size_t sz, T const * dt);

    template <typename T>
    T nanhfsigma(size_t sz, T const * dt);

    template <typename T, typename K>
    void nancount(size_t width, size_t sz, T const * dt, K * out);

    template <typename T, typename K>
    void nanthreshold(size_t width, int threshold, size_t sz, T const * dt, K * out);

    template <typename T>
    T nanmediandeviation(size_t sz, T const * dt);

    template <typename T>
    inline T mediandeviation(size_t sz, T const * dt);
}}
