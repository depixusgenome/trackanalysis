#pragma once
#include <vector>

namespace peakfinding 
{
    struct HistogramPeakFinder
    {
        float peakwidth = .8;
        float threshold = .05;
        std::vector<float> compute(float, float, float, size_t, float const *) const;
    };
}
