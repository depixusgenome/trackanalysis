#include "peakcalling/optimize.hpp"
#include "peakcalling/costfunction.h"


namespace peakcalling { namespace cost
{
    namespace
    {
        Output _cross(float const * bead1, float const * weights1, size_t size1,
                      float const * bead2, float const * weights2, size_t size2,
                      double alpha, double beta, double sig)
        {
            double sum       = 0.;
            double grsum [2] = {0., 0.};

            bool   wgood     = weights1 != nullptr || weights2 != nullptr;
            for(size_t i2 = 0; i2 < size2; ++i2)
                for(size_t i1 = 0; i1 < size1; ++i1)
                {
                    double d = (bead1[i1]-alpha*bead2[i2]-beta)/sig;
                    double w = wgood ? weights1[i1]*weights2[i2] : 1.0;
                    double e = w*std::exp(-.5*d*d);
                    double c = e*d/sig;

                    sum      += e;
                    grsum[0] += c*bead2[i2];
                    grsum[1] += c;
                }

            return std::make_tuple(float(sum), float(grsum[0]), float(grsum[1]));
        }

        Output _norm2(float const * bead2, float const * weights2, size_t size2,
                      double alpha, double sig)
        {
            double norm2  = 0.;
            double grnorm = 0.;

            bool   wgood  = weights2 != nullptr;
            for(size_t i2 = 0; i2 < size2; ++i2)
                for(size_t i1 = 0; i1 < size2; ++i1)
                {
                    double d = (bead2[i1]-bead2[i2])*alpha/sig;
                    double w = wgood ? weights2[i1]*weights2[i2] : 1.0;
                    double e = w*std::exp(-.5*d*d);

                    norm2  += e;
                    grnorm += e*d/sig*(bead2[i2]-bead2[i1]);
                }

            return std::make_tuple(float(norm2), float(grnorm), 0.f);
        }

        float _norm1(float const * bead1, float const * weights1, size_t size1,
                     double sig)
        {
            double norm1 = 0.0;
            bool   wgood  = weights1 != nullptr;
            for(size_t i1 = 0; i1 < size1; ++i1)
                for(size_t i2 = 0; i2 < size1; ++i2)
                {
                    double d = (bead1[i1]-bead1[i2])/sig;
                    double w = wgood ? weights1[i1]*weights1[i2] : 1.0;
                    norm1   += w*std::exp(-.5*d*d);
                }

            return float(norm1);
        }

        Output _computecf(Parameters const & cf, double stretch, double bias,
                          float const * bead1, float const * yvals1, size_t size1,
                          float const * bead2, float const * yvals2, size_t size2)
        {
            auto cost = [](float const * pos1, float const * aweight1, size_t size1,
                           float const * pos2, float const * aweight2, size_t size2,
                           double alpha, double beta, double sig)
                        -> std::tuple<float, float, float>
                {
                    if(size1 == 0 || size2 == 0)
                        return std::make_tuple(1.0f, 0.0f, 0.0f);

                    auto cross = _cross(pos1, aweight1, size1,
                                        pos2, aweight2, size2,
                                        alpha, beta, sig);
                    auto n2 = _norm2(pos2, aweight2, size2, alpha, sig);
                    auto n1 = _norm1(pos1, aweight1, size1, sig);

                    float sum = std::get<0>(cross);
                    float c   = std::sqrt(std::get<0>(n2)*n1);
                    float x   = sum/c;
                    return std::make_tuple(1.-x,
                                           (.5*std::get<1>(n2)*sum/std::get<0>(n2)
                                            -std::get<1>(cross)
                                           )/c,
                                           -std::get<2>(cross)/c);
                };

            auto r1 = cost(bead1, yvals1, size1,
                           bead2, yvals2, size2,
                           stretch, bias, cf.sigma);

            float sumv = 0.f, dx1 = 0.0f, dx2 = 0.0f;
            auto  add = [&](int i, float delta)
            {
                auto val = (bead2[i]*stretch+bias-delta)/cf.sigma;
                auto ex  = std::exp(-.5f*val*val);
                    
                sumv += 1.0f-ex;
                ex   *= val/cf.sigma;
                dx1  += bead2[i]*ex;
                dx2  += ex;
            };

            auto finish = [&](float factor)
            {
                return std::make_tuple(float(std::get<0>(r1) + sumv*factor),
                                       float(std::get<1>(r1) + dx1 *factor),
                                       float(std::get<2>(r1) + dx2 *factor));
            };

            if(cf.singlestrand > 0 && bead1[size1-1] < bead2[size2-1]*stretch+bias)
            {
                float maxv = bead1[size1-1];
                for(int i = int(size2)-1; i >= 0 && bead2[i]*stretch+bias > maxv; --i)
                    add(i, maxv);
                r1 = finish(cf.singlestrand);
            }

            if(cf.baseline > 0 && bead2[0]*stretch+bias < 0)
            {
                sumv = dx1 = dx2 = 0.0f;
                for(int i = 0, ie = int(size2); i < ie && bead2[i]*stretch+bias < 0.f; ++i)
                    add(i, 0.f);
                r1 = finish(cf.baseline);
            }

            if(!cf.symmetric)
                return r1;

            auto r2 = cost(bead2, yvals2, size2, bead1, yvals1, size1, 1./stretch, -bias/stretch,
                           cf.sigma);
            return std::make_tuple(float(std::get<0>(r1) +std::get<0>(r2)),
                                   float(std::get<1>(r1)-(std::get<1>(r2)-std::get<2>(r2)*bias)
                                                         /(stretch*stretch)),
                                   float(std::get<2>(r1) -std::get<2>(r2)/stretch));
        }

        double  _compute(unsigned, double const * x, double * g, void * d)
        {
            auto const & cf = *((optimizer::NLOptCall<Parameters> const *) d);
            auto res = _computecf(*cf.params, x[0], x[1],
                                  cf.beads[0], cf.weights[0], cf.sizes[0],
                                  cf.beads[1], cf.weights[1], cf.sizes[1]);
            g[0] = std::get<1>(res);
            g[1] = std::get<2>(res);
            return std::get<0>(res);
        }
    }

    Terms terms(float alpha, float beta, float sig,
                float const * bead1, float const * weight1,  size_t size1,
                float const * bead2, float const * weight2,  size_t size2)
    {
        auto n1    = std::make_tuple(_norm1(bead1, weight1, size1, sig), 0.f, 0.f);
        auto n2    = _norm2(bead2, weight2, size2, alpha, sig);
        auto cross = _cross(bead1, weight1, size1,
                            bead2, weight2, size2,
                            alpha, beta, sig);
        return std::make_tuple(n1, n2, cross);
    }

    Output compute  (Parameters const & cf,
                     float const * bead1, float const * weights1,  size_t size1,
                     float const * bead2, float const * weights2,  size_t size2)
    {
        return _computecf(cf, cf.current[0], cf.current[1],
                          bead1, weights1, size1,
                          bead2, weights2, size2);
    }

    Output optimize (Parameters const & cf,
                     float const * bead1, float const * weights1,  size_t size1,
                     float const * bead2, float const * weights2,  size_t size2)
    {
        return optimizer::optimize(cf, bead1, weights1, size1, bead2, weights2, size2,
                                   _compute);
    }
}}
