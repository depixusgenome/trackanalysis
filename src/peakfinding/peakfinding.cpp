#include <algorithm>
#include <cmath>
#include "peakfinding.h"

namespace peakfinding
{

std::vector<float> HistogramPeakFinder::compute(
        float        precision,
        float        minv,
        float        binw,
        size_t       sz,
        float const *hist) const
{
    std::vector<float> out;
    long ipk = std::max(std::lround(peakwidth*precision/binw), 0l);
    for(long i = ipk, ie = long(sz)-ipk-1l; i < ie; )
    {
        auto cur = long(std::max_element(hist+i-ipk, hist+std::min(ie, i+ipk+1l)) - hist);
        if(cur == i)
        {
            i = cur+ipk+1l;
            if(hist[cur] >  threshold)
                out.push_back(cur*binw+minv);
        }
        else if(cur < i)
            i = std::max(i+1l, cur+ipk);
        else
            i = cur;
    }
    return out;
}
}
