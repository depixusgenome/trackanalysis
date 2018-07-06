#ifndef SIGNALFILTER_ACCUMULATORS_HPP
#   define SIGNALFILTER_ACCUMULATORS_HPP
#include <boost/accumulators/statistics/rolling_mean.hpp>
#include <boost/accumulators/statistics/mean.hpp>
#include <boost/accumulators/statistics/min.hpp>
#include <boost/accumulators/statistics/max.hpp>
#include <boost/accumulators/statistics/median.hpp>
#include <boost/accumulators/statistics/variance.hpp>
#include <boost/accumulators/statistics/variates/covariate.hpp>
#include <boost/accumulators/statistics/weighted_covariance.hpp>
#include <boost/accumulators/statistics/weighted_moment.hpp>
#include <boost/accumulators/statistics/weighted_mean.hpp>
#include <boost/accumulators/statistics/extended_p_square_quantile.hpp>
#include <boost/accumulators/framework/accumulator_base.hpp>
#include <boost/accumulators/framework/parameters/sample.hpp>
#include <valarray>
#include <list>

#include "signalfilter/accumulators.h"
namespace signalfilter { namespace stats
{
    template <typename T>
    typename T::value_type median(T & items)
    {
        auto nth = items.size()/2;
        switch(items.size())
        {
            case 0: return 0;
            case 1: return items[0];
            case 2: return (typename T::value_type)(.5)*(items[0]+items[1]);
            default:
            {
                auto at  = [&](size_t k) { return items.begin()+k; };
                std::nth_element(at(0), at(nth), items.end());
                if(items.size() % 2 == 0)
                    std::nth_element(at(0), at(nth-1), at(nth));
            }
        }

        if(items.size() % 2 == 1)
            return items[nth];
        else
            return (typename T::value_type)(.5)*(items[nth]+items[nth-1]);
    }

    template <typename T>
    auto median(T begin, T end)
    {
        using S = typename std::remove_cv<
                    typename std::remove_reference<decltype(*begin)>::type
                                         >::type;
        std::vector<S> x(begin, end);
        return median(x);
    }
}}

namespace boost { namespace accumulators {
    BOOST_PARAMETER_KEYWORD(tag, exact_range)
    BOOST_ACCUMULATORS_IGNORE_GLOBAL(exact_range)

    namespace impl
    {
        template<typename Sample>
        struct _MedianDeviation : accumulator_base
        {
            using result_type = Sample;
            _MedianDeviation()
                : _quant(extended_p_square_probabilities = boost::array<double,2>{{1./3., 2./3.}})
            {}
            _MedianDeviation(dont_care) : _MedianDeviation() {}

            template<typename Args>
            void operator ()(Args const & args) { _quant(args[sample]); }

            result_type result(dont_care) const
            {
                auto q0  = quantile(_quant, quantile_probability = 1./3.);
                auto q1  = quantile(_quant, quantile_probability = 2./3.);
                return (q1-q0)*.5;
            }
            private:
                accumulator_set<double, stats<tag::count, tag::extended_p_square_quantile>>
                               _quant;
        };

        template<typename Sample, typename Weight, typename T>
        struct _RExtr : accumulator_base
        {
            using result_type = Sample;
            using list_t      = std::deque<std::pair<Sample,Weight>>;

            template<typename Args>
            _RExtr(Args const & args)
              : _window(args[rolling_window_size])
            {}

            template<typename Args>
            void operator ()(Args const & args)
            {
                Sample samp = args[sample];
                while(_items.size() > 0 && T::test(samp, _items.back().first))
                    _items.pop_back();

                Weight wgt  = args[weight | Weight(1)];
                _items.push_back({samp, wgt});

                while(_items.size() > _window)
                    _items.pop_front();
            }

            result_type result(dont_care) const
            { return  _items.front().first; }

            Weight arg() const
            { return  _items.front().second; }

            private:
                size_t  _window;
                list_t  _items;
        };

        template<typename Sample, typename T>
        struct _RExtrArg : accumulator_base
        {
            using result_type = Sample;

            template<typename Args>
            _RExtrArg(Args const &) {}

            template<typename Args>
            void operator ()(Args const &) {}

            template<typename Args>
            result_type result(Args && args) const
            { return  find_accumulator<T>(args[accumulator]).arg(); }
        };

        template<typename Sample>
        struct _ApproxMedian;

        template<typename Sample>
        struct _ExactMedian : accumulator_base
        {
            friend _ApproxMedian<Sample>;
            using result_type = Sample;
            _ExactMedian() = default;

            _ExactMedian(dont_care) : _ExactMedian() {}

            template<typename Args>
            void operator ()(Args const & args)
            { _items.push_back(args[sample]); }

            result_type result(dont_care) const
            {
                // the order is needlessly const in the current situation
                auto & items = const_cast<std::vector<Sample> &>(_items);
                return ::signalfilter::stats::median(items);
            }

            protected:
                std::vector<Sample> _items;
        };

        template<typename Sample>
        struct _ApproxMedian : accumulator_base
        {
            using result_type = Sample;
            template<typename Args>
            _ApproxMedian(Args const & args)
                : _nmax (args[exact_range | 512])
            {}

            template<typename Args>
            void operator ()(Args const & args)
            {
                if(_nmax >= _exact._items.size())
                    _exact(args);
            }

            template<typename Args>
            result_type result(Args && args) const
            {
                if(_exact._items.size() > _nmax)
                    return median(args[accumulator]);
                else
                    return _exact.result(args);
            };

            private:
                size_t                  _nmax = 0;
                _ExactMedian<Sample>    _exact;
        };
    }

    namespace tag
    {
        struct mediandeviation: depends_on<>
        { using impl = accumulators::impl::_MedianDeviation<mpl::_1>; };

        struct rolling_min : depends_on<>
        {
            template <typename T>
            constexpr static bool test(T a, T b) { return a <= b; }

            using impl = accumulators::impl::_RExtr<mpl::_1, mpl::_2, rolling_min>;
        };

        struct rolling_argmin: depends_on<rolling_min>
        { using impl = accumulators::impl::_RExtrArg<mpl::_2, rolling_min>; };

        struct rolling_max
        {
            template <typename T>
            constexpr static bool test(T a, T b) { return a >= b; }

            using impl = accumulators::impl::_RExtr<mpl::_1, mpl::_2, rolling_max>;
        };

        struct rolling_argmax : depends_on<rolling_min>
        { using impl = accumulators::impl::_RExtrArg<mpl::_2, rolling_max>; };

        struct exact_median: depends_on<>
        { using impl = accumulators::impl::_ExactMedian<mpl::_1>; };

        struct approx_median: depends_on<median>
        { using impl = accumulators::impl::_ApproxMedian<mpl::_1>; };
    }

#   define EXTRACTOR(X)                                     \
    namespace extract { extractor<tag::X> const X = {}; }   \
    using extract::X;

    EXTRACTOR(mediandeviation)
    EXTRACTOR(rolling_min)
    EXTRACTOR(rolling_max)
    EXTRACTOR(rolling_argmin)
    EXTRACTOR(rolling_argmax)
    EXTRACTOR(exact_median)
    EXTRACTOR(approx_median)
#   undef EXTRACTOR
}}

namespace signalfilter { namespace stats
{
    namespace ba  = boost::accumulators;
    namespace bat = boost::accumulators::tag;

    template <typename ...T>
    template <typename C>
    inline acc_t<T...>::acc_t(C const & p)
    {
        for(auto i = std::begin(p), e = std::end(p); i != e; ++i)
            (*this)(*i);
    }

    template <typename ...T>
    template <typename C>
    inline acc_t<T...>::acc_t(size_t sz, C const * p)
    {
        for(size_t i = 0; i < sz; ++i)
            (*this)(p[i]);
    }

    template <typename ...T>
    template <typename Args, typename C>
    acc_t<T...>::acc_t(Args && args, size_t sz, C const * p)
        : self_t(args)
    {
        for(size_t i = 0; i < sz; ++i)
            (*this)(p[i]);
    }

    using mean_t  = acc_t<bat::count, bat::mean>;
    using rm_t    = acc_t<bat::rolling_mean>;

    template <typename T>
    inline auto _star(T const & x) -> decltype(*x) { return *x; }

    template <typename T>
    inline typename std::enable_if<std::is_arithmetic<T>::value, T>::type
    _star(T const & x) { return x; }

    template <typename ...T>
    template <typename C0, typename C1>
    inline wacc_t<T...>::wacc_t(C0 const & p, C1 const & w)
    {
        auto itw = std::begin(w);
        for(auto itp = std::begin(p), e = std::end(p); itp != e; ++itp, ++itw)
            (*this)(_star(itp), ba::weight = _star(itw));
    }

    template <typename ...T>
    template <typename C0, typename C1, typename C2>
    inline wacc_t<T...>::wacc_t(C0 const & p, C1 const & w, C2 const & cv)
    {
        auto itw = std::begin(w);
        auto itc = std::begin(cv);
        for(auto itp = std::begin(p), e = std::end(p); itp != e; ++itp, ++itw)
            (*this)(_star(itp), ba::weight = _star(itw), ba::covariate1 = _star(cv));
    }

    template <typename ...T>
    template <typename T0, typename T1>
    inline wacc_t<T...>::wacc_t(size_t sz, T0 p, T1 w)
    {
        for(size_t i = 0; i  < sz; ++p, ++w, ++i)
            (*this)(_star(p), ba::weight = _star(w));
    };

    template <typename ...T>
    template <typename Args, typename T0, typename T1>
    inline wacc_t<T...>::wacc_t(Args && args, size_t sz, T0 p, T1 w)
        : self_t(args)
    {
        for(size_t i = 0; i  < sz; ++p, ++w, ++i)
            (*this)(_star(p), ba::weight = _star(w));
    };

    template <typename ...T>
    template <typename T0, typename T1, typename T2>
    inline wacc_t<T...>::wacc_t(size_t sz, T0 p, T1 w, T2 cv)
    {
        for(size_t i = 0; i  < sz; ++p, ++w, ++cv, ++i)
            (*this)(_star(p), ba::weight = _star(w), ba::covariate1 = _star(cv));
    };

    template <typename ...T>
    template <typename Args, typename T0, typename T1, typename T2>
    inline wacc_t<T...>::wacc_t(Args && args, size_t sz, T0 p, T1 w, T2 cv)
        : self_t(args)
    {
        for(size_t i = 0; i  < sz; ++p, ++w, ++cv, ++i)
            (*this)(_star(p), ba::weight = _star(w), ba::covariate1 = _star(cv));
    };

    template <typename ... T>
    inline RARolling<T...>::RARolling(size_t ws, bool dir)
    { setup(ws, dir); }

    template <typename ... T>
    template <typename P>
    inline RARolling<T...>::RARolling(size_t ws, P const & ptr, bool dir)
    {
        setup(ws, dir);
        for(size_t i = 0; i < ws-1; ++i)
            operator()(ptr+i);
    }

    template <typename ... T>
    template <typename P, typename W>
    inline RARolling<T...>::RARolling(size_t ws, P const & ptr, W const & wgt, bool dir)
    {
        setup(ws, dir);
        for(size_t i = 0; i < ws-1; ++i)
            operator()(ptr+i, wgt+i);
    }

    template <typename ...T>
    inline void RARolling<T...>::setup(size_t ws, bool dir)
    { _ws  = int(ws); _dir = dir ? -int(_ws) : int(_ws); }

    template <typename ...T>
    template <typename P>
    inline void RARolling<T...>::unsafe(P const * ptr)
    {
        _do(ptr[_dir], -1.);
        _do(ptr[0],     1.);
    }

    template <typename ...T>
    template <typename P, typename W>
    inline void RARolling<T...>::unsafe(P const * ptr, W const * wgt)
    {
        _do(ptr[_dir], -wgt[_dir]);
        _do(ptr[0],     wgt[0]);
    }

    template <typename ...T>
    template <typename P>
    inline void RARolling<T...>::operator() (P const * ptr)
    {
        if(_burn >= _ws)
            _do(ptr[_dir], -1.);
        else
            ++_burn;
        _do(ptr[0], 1.);
    }

    template <typename ...T>
    template <typename P, typename W>
    inline void RARolling<T...>::operator() (P const * ptr, W const * wgt)
    {
        if(_burn >= _ws)
            _do(ptr[_dir], -wgt[_dir]);
        else
            ++_burn;
        _do(ptr[0], wgt[0]);
    }

    template <typename ...T>
    inline void RARolling<T...>::_do(double v, double w)
    { wacc_t<T...>::operator()(v, ba::weight = w); }

    template <typename ...T>
    inline void Rolling<T...>::setup(size_t ws) { _vals.resize(ws); _wgts.resize(ws); }

    template <typename ...T>
    inline void Rolling<T...>::operator() (double val, double wgt)
    {
        if(_burn >= _vals.size())
            _do(_vals[_ind], -_wgts[_ind]);
        else
            ++_burn;
        _do(val, wgt);

        _vals[_ind] = val;
        _wgts[_ind] = wgt;
        _ind = _ind == _vals.size()-1 ? 0 : _ind+1;
    }

    template <typename ...T>
    inline void Rolling<T...>::_do(double v, double w)
    { wacc_t<T...>::operator()(v, ba::weight = w); }

    namespace
    {
        static decltype(auto) wsize = ba::tag::rolling_window::window_size;
    }

    template <typename T, typename C>
    inline auto compute(size_t sz, C const * elems)
    { return ba::extract_result<T>(acc_t<T>(sz, elems)); }

    template <typename T, typename C>
    inline auto compute(C const & elems)
    ->  typename
        std::enable_if<!std::is_arithmetic<C>::value,
                       decltype(ba::extract_result<T>(acc_t<T>(elems)))
                      >::type
    { return ba::extract_result<T>(acc_t<T>(elems)); }

    template <typename T>
    inline auto compute(acc_t<T> const & x)
    { return ba::extract_result<T>(x);  };

    template <typename T>
    inline T hfsigma(size_t sz, T const * dt)
    {
        acc_t<bat::median> quant;
        for(size_t i = size_t(1); i < sz; ++i)
            quant((double) std::abs(dt[i]-dt[i-1]));
        return (T) compute(quant);
    }

    template <typename T>
    inline std::pair<T,bool> nanhfsigma(size_t sz, T const * dt)
    {
        if(sz == 0)
            return {T(0), false};

        size_t i = size_t(0);
        while(i < sz && !std::isfinite(dt[i]))
            ++i;

        if(i >= sz-1)
            return {T(0), false};

        T last = dt[i++];
        while(i < sz && !std::isfinite(dt[i]))
            ++i;

        if(i == sz)
            return {T(0), false};

        acc_t<bat::median> quant;
        quant((double) std::abs(last-dt[i]));
        last = dt[i];
        for(++i; i < sz; ++i)
            if(std::isfinite(dt[i]))
            {
                T cur = dt[i];
                quant((double) std::abs(cur-last));
                last  = cur;
            }
        return {(T) compute(quant), true};
    }

    template <typename T>
    inline T mediandeviation(size_t sz, T const * dt)
    {
#       ifdef _MSC_VER
#           pragma warning( push )
#           pragma warning( disable : 4244 )
#       endif
        acc_t<bat::mediandeviation> quant;
#       ifdef _MSC_VER
#           pragma warning (pop)
#       endif
        for(size_t i = size_t(0); i < sz; ++i)
            quant((double) dt[i]);
        return (T) compute(quant);
    }

    template <typename T>
    inline std::pair<T,bool> nanmediandeviation(size_t sz, T const * dt)
    {
        if(sz == 0)
            return {T(0), false};

        size_t i = size_t(0);
        while(i < sz && !std::isfinite(dt[i]))
            ++i;

        if(i >= sz)
            return {T(0), false};

        acc_t<bat::mediandeviation> quant;
        quant((double) dt[i]);
        for(++i; i < sz; ++i)
            if(std::isfinite(dt[i]))
                quant((double) dt[i]);
        return {(T) compute(quant), true};
    }
}}
#endif
