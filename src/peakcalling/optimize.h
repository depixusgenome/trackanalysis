#pragma once
#include <vector>
#include <tuple>

namespace peakcalling { namespace optimizer
{
    using Output = std::tuple<float, float, float>;

    struct Parameters
    {
        float sigma;
        std::vector<double> lower, current, upper;

        double    xrel    = 1e-4;
        double    frel    = 1e-4;
        double    xabs    = 1e-8;
        double    stopval = 1e-8;
        size_t    maxeval = 100;
    };
}}
