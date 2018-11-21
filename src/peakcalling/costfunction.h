#pragma once
#include "peakcalling/optimize.h"

namespace peakcalling { namespace cost
{
    struct Parameters: public optimizer::Parameters
    {
        bool  symmetric;
        float baseline;
        float singlestrand;
    };

    using Output = optimizer::Output;
    using Terms  = std::tuple<Output, Output, Output>;

    Terms terms(float alpha, float beta, float sig,
                float const * bead1, float const * weight1,  size_t size1,
                float const * bead2, float const * weight2,  size_t size2);
    Output compute (Parameters const &,
                    float const *, float const *, size_t,
                    float const *, float const *, size_t);
    Output optimize(Parameters const &,
                    float const *, float const *, size_t,
                    float const *, float const *, size_t);
}}
