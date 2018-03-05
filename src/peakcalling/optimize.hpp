#include <limits>
#include <sstream>
#ifdef _MSC_VER
# pragma warning( push )
# pragma warning( disable : 4267)
# include <nlopt.hpp>
# pragma warning( pop )
#else
# pragma GCC diagnostic push
# pragma GCC diagnostic ignored "-Wswitch-enum"
# include <nlopt.hpp>
# pragma GCC diagnostic pop
#endif
#include <pybind11/pybind11.h>
#include "peakcalling/optimize.h"

namespace peakcalling { namespace optimizer
{
    template <typename T = Parameters>
    struct NLOptCall
    {
        T     const * params;
        float const * beads[2];
        float const * weights[2];
        size_t        sizes[2];
    };

    template <typename T>
    Output optimize (T     const & cf,
                     float const * bead1, float const * weight1, size_t size1,
                     float const * bead2, float const * weight2, size_t size2,
                     double  fcn(unsigned, double const *, double *, void *)
                    )
    {
        double minf = std::numeric_limits<double>::max();
        std::vector<double> tmp = cf.current;

        if(size1 > 0 && size2 > 0)
        {
            nlopt::opt opt(nlopt::LD_LBFGS, size_t(2));
            opt.set_xtol_rel(cf.xrel);
            opt.set_ftol_rel(cf.frel);
            opt.set_xtol_abs(cf.xabs);
            opt.set_stopval (cf.stopval);
            opt.set_maxeval (int(cf.maxeval));

            NLOptCall<T> call = {&cf, {bead1, bead2}, {weight1, weight2}, {size1, size2}};
            opt.set_min_objective(fcn, static_cast<void*>(&call));

            std::ostringstream stream;
            for(size_t i = size_t(0), e = cf.lower.size(); i < e; ++i)
            {
                if(cf.lower[i] > cf.current[i])
                    stream << "lower[" << i << "] > current[" <<i << "]: "
                           << cf.lower[i] << " > " << cf.current[i] << std::endl;
                if(cf.upper[i] < cf.current[i])
                    stream << "current[" << i << "] > upper[" <<i << "]: "
                           << cf.current[i] << " > " << cf.upper[i] << std::endl;
            }
            std::string err = stream.str();
            if(err.size())
                throw pybind11::value_error(err);

            opt.set_lower_bounds(cf.lower);
            opt.set_upper_bounds(cf.upper);

            opt.optimize(tmp, minf);
        }
        return std::make_tuple(float(minf), float(tmp[0]), float(tmp[1]));
    }
}}
