#pragma once
#include <utility>
#include <vector>

namespace eventdetection { namespace merging {
    using ints_t = std::vector<std::pair<size_t, size_t>>;

    struct  HeteroscedasticEventMerger
    {
        float confidence   = 0.1f;
        float minprecision = 5e-4f;
        void  run(float const *,  ints_t &) const;
    };

    struct PopulationMerger
    {
        float percentile = 66.0f;
        void  run(float const *,  ints_t &) const;
    };

    struct ZRangeMerger
    {
        float percentile = 80.0f;
        void  run(float const *,  ints_t &) const;
    };

    struct MultiMerger
    {
        HeteroscedasticEventMerger stats;
        PopulationMerger           pop;
        ZRangeMerger               range;

        void  run(float const *,  ints_t &) const;
    };
}}
