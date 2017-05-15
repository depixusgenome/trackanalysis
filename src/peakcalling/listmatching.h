#pragma once
#include "peakcalling/optimize.h"

namespace peakcalling { namespace match
{
    using optimizer::Parameters;
    using Output = std::vector<size_t>;
    Output compute (float, float const *, size_t, float const *, size_t);

    size_t nfound  (float, float const *, size_t, float const *, size_t);

    std::tuple<double, double, double, size_t>
    distance  (float, float, float, float const *, size_t, float const *, size_t);

    optimizer::Output optimize(Parameters const &, float const *, size_t,
                               float const *, size_t);
}}
