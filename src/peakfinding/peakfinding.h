#pragma once
#include <vector>

namespace peakfinding 
{
    struct HistogramPeakFinder
    {
        float peakwidth = .8f;
        float threshold = .05f;
        std::vector<float> compute(float, float, float, size_t, float const *) const;
    };
}
