#include "peakcalling/peakiterator.h"

namespace peakcalling { namespace match {

template <typename T1, typename T2>
bool _next(T1 & self, T2 && fcn, size_t *inds, float *params)
{
    float stretch = 0.0f, bias = 0.0f;
    bool  good    = false;
    while(!good && self.i2r < self.nref)
    {
        stretch = (self.ref[self.i2r] - self.ref[self.i1r])/(self.exp[self.i2e]-self.exp[self.i1e]);
        bias    = self.exp[self.i1e]  - self.ref[self.i1r]/(stretch != 0.0f ? stretch : 1e-7);
        good    = fcn(stretch, bias);

        if(inds != nullptr)
        {
            inds[0] = self.i1r; inds[1] = self.i1e; inds[2] = self.i2r; inds[3] = self.i2e;
        }

        if(self.i2e == self.nexp-1 && self.i1e == self.nexp-2)
        {
            self.i1e = 0;
            self.i2e = 1;
            if(self.i2r == self.nref-1)
            {
                ++self.i1r;
                self.i2r = self.i1r+1;
            } else
                ++self.i2r;
        } else if(self.i2e == self.nexp-1)
        {
            ++self.i1e;
            self.i2e = self.i1e+1;
        } else
            ++self.i2e;
    }

    if(params)
    {
        params[0] = stretch;
        params[1] = bias;
    }
    return good;
}

bool Iterator::next(size_t *inds, float *params)
{
    auto fcn = [this](float stretch, float bias)
    {
        return (
                stretch    > minstretch
                && stretch < maxstretch
                && bias    > minbias
                && bias    < maxbias
               );
    };
    return _next(*this, fcn, inds, params);
}

bool BoundedIterator::next(size_t *inds, float *params)
{
    auto fcn = [this](float & stretch, float & bias)
    {
        stretch = std::max(minstretch, std::min(maxstretch, stretch));
        bias    = std::max(minbias,    std::min(maxbias,    bias));
        return (
                std::abs((exp[i2e]-bias)*stretch - ref[i2r]) < window
                && std::abs((exp[i1e]-bias)*stretch - ref[i1r]) < window
               );
    };
    return _next(*this, fcn, inds, params);
}
}}
