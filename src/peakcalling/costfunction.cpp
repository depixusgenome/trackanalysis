#include "peakcalling/optimize.hpp"
#include "peakcalling/costfunction.h"


namespace peakcalling { namespace cost
{
    namespace
    {
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

                    double sum       = 0.;
                    double norm1     = 0.;
                    double grsum [2] = {0., 0.};
                    double grnorm    = 0.;

                    auto   weights = [](auto const & aweight, auto size)
                    {
                        if(aweight == nullptr)
                            return std::vector<float>(size, 1.);
                        return std::vector<float>(aweight, aweight+size);
                    };

                    auto weights1 = weights(aweight1, size1),
                         weights2 = weights(aweight2, size2);

                    for(size_t i2 = 0; i2 < size2; ++i2)
                    {
                        for(size_t i1 = 0; i1 < size1; ++i1)
                        {
                            double d = (pos1[i1]-alpha*pos2[i2]-beta)/sig;
                            double w = weights1[i1]*weights2[i2];
                            double e = w*std::exp(-.5*d*d);
                            double c = e*d/sig;

                            sum      += e;
                            grsum[0] += c*pos2[i2];
                            grsum[1] += c;
                        }

                        for(size_t i1 = 0; i1 < size2; ++i1)
                        {
                            double d = (pos2[i1]-pos2[i2])*alpha/sig;
                            double w = weights2[i1]*weights2[i2];
                            double e = w*std::exp(-.5*d*d);

                            norm1  += e;
                            grnorm += e*d/sig*(pos2[i2]-pos2[i1]);
                        }
                    }

                    double norm2 = 0.0;
                    for(size_t i1 = 0; i1 < size1; ++i1)
                        for(size_t i2 = 0; i2 < size1; ++i2)
                        {
                            double d = (pos1[i1]-pos1[i2])/sig;
                            double w = weights1[i1]*weights1[i2];
                            norm2   += w*std::exp(-.5*d*d);
                        }

                    double c = std::sqrt(norm1*norm2);
                    double x = sum/c;
                    return std::make_tuple(float(1.-x),
                                           float((.5*grnorm*sum/norm1-grsum[0])/c),
                                           float(-grsum[1]/c));
                };

            auto r1 = cost(bead1, yvals1, size1,
                           bead2, yvals2, size2,
                           stretch, bias, cf.sigma);
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
