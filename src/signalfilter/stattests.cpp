#include <boost/math/distributions/students_t.hpp>
#include <boost/math/distributions/normal.hpp>
#include "signalfilter/stattests.h"

namespace bm = boost::math;

namespace samples
{
    namespace normal
    {
        namespace
        {
            template <typename T>
            inline auto _level(std::pair<T,float> val)
            {
                bm::students_t dist(val.first);
                return bm::cdf(dist, std::abs(val.second));
            }

            template <typename T>
            inline bool _isequal(float alpha, std::pair<T,float> val)
            {
                auto lev = _level(val);
                return lev > alpha*.5 && lev < 1.-alpha*.5;
            }

            template <typename T>
            inline bool _islower(float alpha, std::pair<T,float> val)
            { return _level(val) < alpha; }

            float _cntnorm(float c1, float c2)
            { return std::sqrt(c1*c2/(c1+c2)); }
        }

        namespace knownsigma
        {
            float value(bool bequal, Input const & left, Input const & right)
            {
                auto val = (left.mean-right.mean) * _cntnorm(left.count, right.count);
                return bequal && val < 0. ? -val : val;
            }

            float threshold(bool bequal, float alpha, float sigma)
            { return bm::quantile(bm::normal(0., sigma), bequal ? 1. - alpha * .5 : alpha); }

            float threshold(bool bequal, float alpha, float sigma, size_t cnt1, size_t cnt2)
            { return threshold(bequal, alpha, sigma)/_cntnorm(cnt1, cnt2); }

            bool isequal(float alpha, float sigma, Input const & left, Input const & right)
            { return value(true, left, right) < threshold(true, alpha, sigma); }
        }

        namespace homoscedastic
        {
            std::pair<size_t, float> value(Input const & left, Input const & right)
            {
                auto oneS  = [](auto const x) { return x.sigma*x.sigma*(x.count-1); };
                auto free  = left.count+right.count-2;
                auto sigma = std::sqrt((oneS(left)+oneS(right))/free);
                auto t     = (left.mean-right.mean) / sigma
                           * _cntnorm(left.count, right.count);
                return {free, t};
            }

            bool isequal(float alpha, Input const & left, Input const & right)
            { return _isequal(alpha, value(left, right)); }

            bool islower(float alpha, Input const & left, Input const & right)
            { return _islower(alpha, value(left, right)); }

            bool isgreater(float alpha, Input const & left, Input const & right)
            { return !_islower(alpha, value(left, right)); }
        }

        namespace heteroscedastic
        {
            std::pair<float,float> value(Input const & left, Input const & right)
            {
                auto sigovern = [](auto const &x)           { return x.sigma*x.sigma/x.count; };
                auto div      = [](auto a, auto const &b)   { return a*a/(b.count-1); };

                auto sonL   = sigovern(left);
                auto sonR   = sigovern(right);
                auto sumson = sonL+sonR;
                auto free   = sumson*sumson/(div(sonL, left)+div(sonR, right));
                auto t      = (left.mean-right.mean) / std::sqrt(sumson);
                return {free, t};
            }

            bool isequal(float alpha, Input const & left, Input const & right)
            { return _isequal(alpha, value(left, right)); }

            bool islower(float alpha, Input const & left, Input const & right)
            { return _islower(alpha, value(left, right)); }

            bool isgreater(float alpha, Input const & left, Input const & right)
            { return !_islower(alpha, value(left, right)); }
        }
    }
}
