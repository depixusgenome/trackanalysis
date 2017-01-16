#pragma once
#include <vector>
#include <tuple>

namespace peakcalling { namespace match
{
    using Output = std::vector<size_t>;
    Output compute (float, float const *, size_t, float const *, size_t);
}}
