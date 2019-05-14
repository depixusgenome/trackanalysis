#include <limits>
#include <map>
#include "signalfilter/signalfilter.h"
#include "signalfilter/accumulators.hpp"
namespace signalfilter
{
    namespace
    {
        using namespace signalfilter::stats;
        struct _BaseQuality
        {
            _BaseQuality()                     = delete;
            _BaseQuality(_BaseQuality const &) = default;
            template <typename T>
            _BaseQuality(T const & cf, size_t w, bool norm)
                : _prec  (std::abs(cf.precision))
                , _norm  (norm)
                , _pow   (-int(cf.power))
                , _est   (1)
                , _qual  (w)
                , _factor(1.)
                , _bias  (0.)
            {}

            protected:
                void setup(size_t wl, bool dir)
                {
                    _est.setup(wl, dir);
                    if(_norm)
                    {
                        _factor = wl <= 1 ? 0  : wl/(wl-1.);
                        _bias   = wl <= 1 ? 4. : 2.*std::sqrt(wl)/(wl-1.);
                    }
                }

                std::pair<double, double> add(double wgt, double mean) const
                {
                    constexpr auto nm = std::numeric_limits<float>::max();
                    wgt = wgt*_factor+_bias;
                    if(!std::isfinite(wgt))
                        return {0., mean};
                    else if(wgt <= std::numeric_limits<float>::min())
                        return {nm, mean};

                    auto pw = std::pow(wgt, _pow);
                    return {pw > nm || !std::isfinite(pw) ? nm : pw, mean};
                }

                double                              _prec;
                bool                                _norm;
                int                                 _pow;
                RARolling<bat::mean>                _est;
                Rolling  <bat::mean>                _qual;
                double                              _factor = 1.;
                double                              _bias   = 0.;
        };

        template <typename T>
        struct _CovQuality: public T
        {
            _CovQuality()                       = default;
            _CovQuality(_CovQuality<T> const &) = default;
            template <typename K>
            _CovQuality(K const & args)
                : T     (args)
                , _var  (1)
                , _covar(1)
            {}

            void setup(size_t wl, bool dir)
            {
                T::setup(wl, dir);
                _var  .setup(wl);
                _covar.setup(wl);
            }

            void operator()(size_t i, float const * xd)
            {
                _var(double(i));
                _covar(xd[0]*i);
                T::operator()(i, xd);
            }

            std::pair<double, double> get() const
            {
                auto r     = T::get();
                auto x     = ba::mean(_var);
                auto covar = ba::mean(_covar)-x*r.second;
                auto x2dev = ba::moment<2>(_var)-x*x;
                r.second   = x2dev != 0. ? covar/x2dev
                           : covar == 0. ? std::numeric_limits<float>::min()
                                         : std::numeric_limits<float>::max();
                return r;
            }

            private:
                Rolling<bat::mean, bat::moment<2>>  _var;
                Rolling<bat::mean>                  _covar;
        };

        struct _BaseFunc
        {
            _BaseFunc()                  = default;
            _BaseFunc(_BaseFunc &&)      = default;
            _BaseFunc(_BaseFunc const &) = default;

            _BaseFunc(size_t nx, float * xd, size_t nv)
                : _sz(nx), _xd(xd), _m0(0., nv), _m1(0., nv)
            {}

            size_t          size()                   const { return _sz;     }
            float const *   get (int i, int)         const { return _xd+i;   }
            void            set (int i, double v)          { _xd[i] = float(v); }

            template <typename T>
            void   add (T const & qual, int i, int j)
            { add(qual.get(), i, j); }

            void   add (std::pair<double,double> pair, int i, int)
            {
                _m0[i]  += pair.first;
                auto rho = pair.first/_m0[i];
                _m1[i]   = pair.second*rho + _m1[i]*(1.-rho);
            }

            void finish()
            {
                if(_sz == _m1.size())
                    for(size_t i = 0; i < _sz; ++i)
                        _xd[i] = float(_m1[i]);
            }

            protected:
                size_t                _sz;
                float               * _xd;
                std::valarray<double> _m0, _m1;
        };

        template <typename T0, typename T1>
        auto _qual(T0 const & cf, bool dir)
        {
            std::valarray<T1> res(T1(cf), cf.estimators.size());
            for(size_t i = 0; i < res.size(); ++i)
                res[i].setup(cf.estimators[i], dir);
            return res;
        }
    }

    namespace forwardbackward
    {
        namespace
        {
            struct _Quality: _BaseQuality
            {
                _Quality(Args const & cf) : _BaseQuality(cf, cf.window, cf.normalize) {}
                using _BaseQuality::_BaseQuality;
                using _BaseQuality::setup;

                void operator()(size_t, float const * xd)
                {
                    _est (xd);
                    auto x = (xd[0]-ba::mean(_est))/_prec;
                    _qual(x*x);
                }

                auto get() const
                {
                    auto mean = ba::mean(_est);
                    auto wgt  = ba::mean(_qual);
                    return _BaseQuality::add(wgt, mean);
                }
            };
        }

        template <typename T, typename Q>
        void run(Args cf, T fcn)
        {
            int const  nx  ((int)fcn.size());
            int const  ne  ((int)cf.estimators.size());
            auto       qual(_qual<Args,Q>(cf, true));

            auto apply  = [&qual,&fcn,ne](int i)
                        {
                            for(int j = 0; j < ne; ++j)
                            {
                                qual[j](i, fcn.get(i,j));
                                fcn.add(qual[j], i, j);
                            }
                        };

            for(int i = 0; i < nx; ++i)
                apply(i);

            qual = _qual<Args,Q>(cf, false);
            for(int i = nx-1; i >= 0; --i)
                apply(i);

            fcn.finish();
        }

        void run(Args const & cf, size_t nx, float *xd)
        {
            _BaseFunc func(nx, xd, nx);
            if(cf.derivate)
                run<_BaseFunc,_CovQuality<_Quality>>(cf, func);
            else
                run<_BaseFunc,_Quality>(cf, func);
        }
    }

    namespace nonlinear
    {
        namespace
        {
            struct _Quality: _BaseQuality
            {
                _Quality(Args const & cf) : _BaseQuality(cf, 1, true) {}
                using _BaseQuality::_BaseQuality;

                void setup(size_t wl, bool dir)
                {
                    _BaseQuality::setup(wl, dir);
                    _qual.setup(wl);
                }

                void operator()(size_t, float const * xd)
                {
                    _est (xd);
                    auto x = xd[0]/_prec;
                    _qual(x*x);
                }

                auto get() const
                {
                    auto mean = ba::mean(_est);
                    auto wgt  = ba::mean(_qual)-(mean/_prec)*(mean/_prec);
                    return _BaseQuality::add(wgt, mean);
                }
            };

            struct _MovingFunc: public _BaseFunc
            {
                _MovingFunc(Args const & cf, size_t nx, float * xd)
                    : _BaseFunc(nx, xd, cf.estimators[cf.estimators.size()-1])
                    , _k  (0)
                    , _nv (cf.estimators[cf.estimators.size()-1])
                    , _inc(cf.estimators.size())
                {
                    for(size_t j = 0; j < _inc.size(); ++j)
                        _inc[j] = _nv-cf.estimators[j]+1;
                }

                template <typename T>
                void   add(T const & qual, size_t i, size_t j)
                {   add(qual.get(), i, j); }

                void   add(std::pair<double,double> val, size_t, size_t j)
                {
                    _BaseFunc::add(val, int(_k), int(j));
                    _BaseFunc::add(val, int((_k+_inc[j]) % _nv), int(j));
                }

                auto compute()
                {
                    _k      = (_k+1) % _nv;
                    auto r  = _m1[_k];
                    _m1[_k] = _m0[_k] = 0.;
                    return r;
                }

                private:
                    size_t                _k, _nv;
                    std::valarray<size_t> _inc;
            };
        }

        template <typename T, typename Q>
        void run(Args const & cf, T & fcn)
        {
            int const ne = (int) cf.estimators.size();
            int const nv = (int) cf.estimators[ne-1];
            int const nx = (int) fcn.size();
            if(nv >= nx)
                return;

            auto qual(_qual<Args,Q>(cf, true));

            auto update = [ne, &qual, &fcn](int i)
                        {
                            for(int j = 0; j < ne; ++j)
                                qual[j](i, fcn.get(i, j));
                        };
            auto apply  = [ne, &qual, &fcn](int i)
                        {
                            for(int j = 0; j < ne; ++j)
                                fcn.add(qual[j], i, j);
                            return fcn.compute();
                        };

            decltype(apply(0)) val = 0;
            for(int i = 0; i < nv; ++i)
            {
                update(i);
                val = apply (i);
            }

            for(int i = nv; i < nx; ++i)
            {
                update(i);
                fcn.set(i-nv, val);
                val = apply(i);
            }
            fcn.set(nx-nv, val);

            for(int i = nx-nv+1; i < nx; ++i)
                fcn.set(i, apply (i));

            fcn.finish();
        }

        void run(Args const & cf, size_t nx, float * xd)
        {
            _MovingFunc fcn(cf, nx, xd);
            if(cf.derivate)
                run<_MovingFunc,_CovQuality<_Quality>>(cf, fcn);
            else
                run<_MovingFunc,_Quality>(cf, fcn);
        }
    }

    namespace clip
    {
        void run(Args const & cf, size_t sz, float * data)
        {
            bool    looking = true;
            float * start   = nullptr;
            auto    y       = data;
            for(auto e = y+sz; y != e; ++y)
                if((y[0] >= cf.minval && y[0] <= cf.maxval) ^ looking)
                {
                    if(looking)
                        start = y-1;
                    else
                    {
                        if(y >= data)
                            for(auto yc = start+1; yc != y; ++yc)
                                *yc = *start;
                        else
                            for(auto yc = start+1; yc != y; ++yc)
                                *yc = *y;
                        start = nullptr;
                    }
                }

            if(start >= data)
                for(auto yc = start+1; yc != y; ++yc)
                    *yc = *start;
        }
    }
}
