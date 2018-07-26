#pragma once
#include <valarray>
#include <vector>
#include <algorithm>

namespace eventdetection {  namespace splitting {

using grade_t = std::valarray<float>;
using ints_t  = std::vector<std::pair<size_t, size_t>>;
using data_t  = std::tuple<float const *, size_t>;
struct IntervalExtensionAroundRange
{
    size_t extensionwindow = 3;
    double extensionratio  = 1;
    ints_t compute(float, data_t, ints_t &&) const;
};

struct DerivateSplitDetector: public IntervalExtensionAroundRange
{
    size_t gradewindow     = 3;
    double percentile      = 75.;
    double distance        = 2.;

    float  threshold(float, grade_t const &) const;
    void   grade    (float, grade_t &)       const;
    ints_t compute  (float, data_t)          const;
};

struct ChiSquareSplitDetector: public IntervalExtensionAroundRange
{
    size_t gradewindow     = 5;
    double confidence      = .1;

    float  threshold(float) const;
    void   grade    (float, grade_t &) const;
    ints_t compute  (float, data_t)    const;
};

struct MultiGradeSplitDetector: public IntervalExtensionAroundRange
{
    DerivateSplitDetector  derivate;
    ChiSquareSplitDetector chisquare;
    size_t                 minpatchwindow = 5;

    void   grade  (float, grade_t &) const;
    ints_t compute(float, data_t)    const;
};
}}
