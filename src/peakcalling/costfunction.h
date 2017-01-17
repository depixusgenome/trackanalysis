#pragma once
#include <vector>
#include <tuple>

namespace peakcalling { namespace cost
{
    struct Parameters
    {
        bool  symmetric;
        float sigma;
        float stretch;
        float bias;
    };

    struct NLOptCall
    {
        bool  symmetric;
        float sigma;
        float const * beads[2];
        size_t        sizes[2];

        std::vector<double> lower, current, upper;

        double    xrel    = 1e-4;
        double    frel    = 1e-4;
        double    xabs    = 1e-8;
        double    stopval = 1e-8;
        size_t    maxeval = 100;
    };

    using Output = std::tuple<float,float,float>;

    Output compute(Parameters, float const *, size_t, float const *, size_t);
    Output optimize(NLOptCall const & cf);
}}
