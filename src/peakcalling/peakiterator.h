#pragma once
#include <cstddef>
#include <tuple>

namespace peakcalling { namespace match {
template <typename T1, typename T2>
bool _next(T1 &, T2 &&, size_t *, float *);

struct Iterator
{
    float         minstretch, maxstretch, minbias, maxbias;
    float const * ref;  size_t nref;
    float const * exp;  size_t nexp;
    Iterator():
        minstretch(800.0f), maxstretch(1300.0f),
        minbias(-.01f),     maxbias(.01f),
        ref(nullptr),       nref(0u),
        exp(nullptr),       nexp(0u),
        i1r(0u),            i2r(1u),
        i1e(0u),            i2e(1u)
    {}

    bool next(size_t *inds, float *params);

    protected:
        template <typename T1, typename T2>
        friend bool _next(T1 &, T2 &&, size_t *, float *);

        size_t i1r, i2r, i1e, i2e;
};

struct BoundedIterator : public Iterator
{
    float window;
    bool next(size_t *inds, float *params);
};
}}
