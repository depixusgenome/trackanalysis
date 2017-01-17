#include <limits>
#include <nlopt.hpp>
#include "peakcalling/costfunction.h"

namespace peakcalling { namespace cost
{
    namespace
    {
        double  _compute(unsigned, double const * x, double * g, void * d)
        {
            NLOptCall const & cf = *((NLOptCall const *) d);
            auto res = compute({cf.symmetric, float(x[0]), float(x[1]), cf.sigma},
                               cf.beads[0], cf.sizes[0], cf.beads[1], cf.sizes[1]);
            g[0] = std::get<1>(res);
            g[1] = std::get<2>(res);
            return std::get<0>(res);
        }
    }

    std::tuple<float,float,float>
    compute  (Parameters cf,
              float const * bead1, size_t size1,
              float const * bead2, size_t size2)
    {
        auto cost = [](float const * pos1, size_t size1,
                       float const * pos2, size_t size2,
                       double alpha, double beta, double sig)
                    -> std::tuple<float, float, float>
            {
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
                        double d = (pos1[i1]-pos1[i2])*alpha/sig;
                        norm2 += std::exp(-.5*d*d);
                    }

                double c = std::sqrt(norm1*norm2);
                double x = sum/c;
                return {float(1.-x),
                        float((.5*grnorm*sum/norm1-grsum[0])/c),
                        float(-grsum[1]/c)};
            };

        auto r1 = cost(bead1, size1, bead2, size2, cf.stretch, cf.bias, cf.sigma);
        if(!cf.symmetric)
            return r1;

        auto r2 = cost(bead2, size2, bead1, size1, cf.stretch, cf.bias, cf.sigma);
        return {std::get<0>(r1) +std::get<0>(r2),
                std::get<1>(r1)-(std::get<1>(r2)-std::get<2>(r2)*cf.bias)/(cf.stretch*cf.stretch),
                std::get<2>(r1) -std::get<2>(r2)/cf.stretch};
    }

    std::tuple<float,float> optimize(NLOptCall const & cf)
    {
        nlopt::opt opt(nlopt::LD_LBFGS, 2);
        opt.set_xtol_rel(cf.xrel);
        opt.set_ftol_rel(cf.frel);
        opt.set_xtol_abs(cf.xabs);
        opt.set_stopval (cf.stopval);
        opt.set_maxeval (cf.maxeval);
        opt.set_min_objective(_compute, const_cast<void*>(static_cast<const void *>((&cf))));

        opt.set_lower_bounds(cf.lower);
        opt.set_upper_bounds(cf.upper);

        double minf = std::numeric_limits<double>::max();
        std::vector<double> tmp = cf.current;
        opt.optimize(tmp, minf);
        return {float(tmp[0]), float(tmp[1])};
    }
}}
