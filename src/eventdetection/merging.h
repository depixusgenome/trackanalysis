#pragma once
#include <utility>
#include <vector>

namespace eventdetection { namespace merging {
    using INTERVALS = std::vector<std::pair<size_t, size_t>>;

    struct  HeteroscedasticEventMerger
    {
        float confidence   = 0.1f;
        float minprecision = 5e-4f;
        void  run(float const *data,  INTERVALS & intervals) const;
    };

    struct PopulationMerger
    {
        float percentile = 66.0f;
        void  run(float const *data,  INTERVALS & intervals) const;
    };

    struct ZRangeMerger
    {
        float percentile = 80.0f;
        void  run(float const *data,  INTERVALS & intervals) const;
    };

    struct MultiMerger
    {
        HeteroscedasticEventMerger stats;
        PopulationMerger           pop;
        ZRangeMerger               range;

        void  run(float const *data,  INTERVALS & intervals) const;
    };
}}
