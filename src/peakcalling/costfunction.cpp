#include "peakcalling/optimize.hpp"
#include "peakcalling/costfunction.h"

namespace peakcalling { namespace cost
{
    namespace
    {
        Output _computecf  (Parameters const & cf, double stretch, double bias,
                            float const * bead1, size_t size1,
                            float const * bead2, size_t size2)
        {
            auto cost = [](float const * pos1, size_t size1,
                           float const * pos2, size_t size2,
                           double alpha, double beta, double sig)
                        -> std::tuple<float, float, float>
                {
                    if(size1 == 0 || size2 == 0)
                        return std::make_tuple(1.0f, 0.0f, 0.0f);

                    double sum       = 0.;
                    double norm1     = 0.;
                    double grsum [2] = {0., 0.};
                    double grnorm    = 0.;
                    for(size_t i2 = 0; i2 < size2; ++i2)
                    {
                        for(size_t i1 = 0; i1 < size1; ++i1)
                        {
                            double d = (pos1[i1]-alpha*pos2[i2]-beta)/sig;
                            double e = std::exp(-.5*d*d);
                            double c = e*d/sig;

                            sum      += e;
                            grsum[0] += c*pos2[i2];
                            grsum[1] += c;
                        }

                        for(size_t i1 = 0; i1 < size2; ++i1)
                        {
                            double d = (pos2[i1]-pos2[i2])*alpha/sig;
                            double e = std::exp(-.5*d*d);

                            norm1  += e;
                            grnorm += e*d/sig*(pos2[i2]-pos2[i1]);
                        }
                    }

                    double norm2 = 0.0;
                    for(size_t i1 = 0; i1 < size1; ++i1)
                        for(size_t i2 = 0; i2 < size1; ++i2)
                        {
                            double d = (pos1[i1]-pos1[i2])/sig;
                            norm2 += std::exp(-.5*d*d);
                        }

                    double c = std::sqrt(norm1*norm2);
                    double x = sum/c;
                    return std::make_tuple(float(1.-x),
                                           float((.5*grnorm*sum/norm1-grsum[0])/c),
                                           float(-grsum[1]/c));
                };

            auto r1 = cost(bead1, size1, bead2, size2, stretch, bias, cf.sigma);
            if(!cf.symmetric)
                return r1;

            auto r2 = cost(bead2, size2, bead1, size1, 1./stretch, -bias/stretch,
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
                                  cf.beads[0], cf.sizes[0],
                                  cf.beads[1], cf.sizes[1]);
            g[0] = std::get<1>(res);
            g[1] = std::get<2>(res);
            return std::get<0>(res);
        }
    }

    Output compute  (Parameters const & cf,
                     float const * bead1, size_t size1,
                     float const * bead2, size_t size2)
    { return _computecf(cf, cf.current[0], cf.current[1], bead1, size1, bead2, size2); }

    Output optimize (Parameters const & cf,
                     float const * bead1, size_t size1,
                     float const * bead2, size_t size2)
    { return optimizer::optimize(cf, bead1, size1, bead2, size2, _compute); }
}}
