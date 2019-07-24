#include <boost/math/distributions/students_t.hpp>
#include <boost/math/distributions/normal.hpp>
#include "eventdetection/stattests.h"
namespace bm = boost::math;

namespace samples
{
    namespace normal
    {
        namespace
        {
            template <typename T>
            inline float _level(std::pair<T, float> val)
            {
                // The degree-of-freedom (arg passed to boost's `dist()`) must be > 0
                auto ans = double(val.first);
                if (std::isfinite(ans) && ans > 0)
                {
                    bm::students_t dist(ans);
                    return float(bm::cdf(dist, std::abs(val.second)));
                }
                return 1.;
            }

            template <typename T>
            inline bool _isequal(float alpha, std::pair<T,float> val)
            {
                auto lev = _level(val);
                return lev > alpha*.5f && lev < 1.0f-alpha*.5f;
            }

            template <typename T>
            inline bool _islower(float alpha, std::pair<T,float> val)
            { return _level(val) < alpha; }

            float _cntnorm(size_t c1, size_t c2)
            { return std::sqrt(float(c1*c2)/float(c1+c2)); }
        }

        namespace knownsigma
        {
            float value(bool bequal, Input const & left, Input const & right)
            {
                auto val = (left.mean-right.mean) * _cntnorm(left.count, right.count);
                return bequal && val < 0.f ? -val : val;
            }

            float threshold(bool bequal, float alpha, float sigma)
            { return float(bm::quantile(bm::normal(0.f, sigma), bequal ? 1.0f - alpha * .5f : alpha)); }

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

            float  threshold(float val) { return 1.0f-val*.5f; }

            float  tothresholdvalue(Input const & left, Input const & right)
            {
                if(left.count < 2 || right.count < 2)
                    return 1.0f;

                float val = _level(value(left, right));
                return val < .5f ? 1.0f-val : val;
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

            float  threshold(float val) { return 1.0f-val*.5f; }

            float  tothresholdvalue(Input const & left, Input const & right)
            {
                if(right.count == 1 || left.count == 1)
                    return 1.;

                float val = _level(value(left, right));
                return val < .5f ? 1.0f-val : val;
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
