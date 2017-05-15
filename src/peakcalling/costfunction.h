#pragma once
#include "peakcalling/optimize.h"

namespace peakcalling { namespace cost
{
    struct Parameters: public optimizer::Parameters
    {
        bool symmetric;
    };

    using Output = optimizer::Output;

    Output compute (Parameters const &, float const *, size_t, float const *, size_t);
    Output optimize(Parameters const &, float const *, size_t, float const *, size_t);
}}
