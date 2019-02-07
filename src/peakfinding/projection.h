#pragma once
#include <vector>
#include <tuple>
#include <algorithm>
#include "peakfinding/peakfinding.h"

namespace peakfinding { namespace projection {
    using cycles_t     = std::vector<std::pair<size_t, float const*>>;

    struct BeadProjectionData
    {
        std::vector<float> histogram;
        std::vector<float> bias;
        float              minvalue;
        float              binwidth;
        std::vector<float> peaks;
    };

    struct DigitizedData
    {
        size_t           oversampling;
        float            precision;
        float            delta;
        size_t           nbins;
        std::vector<int> digits;
    };

    /* Digitize data.
     *
     * Values become:
     *
     *                                                   (x-minedge)
     *  for minedge ≤ x < maxedge:      ix =  _____________________________________
     *                                          (maxedge-minedge)*nbins*2^oversampling                            
     *  for x < minedge or x ≥ maxedge: ix = -1
     */
    struct Digitizer
    {
        size_t oversampling;
        float  precision;
        float  minedge;
        float  maxedge;
        size_t nbins;
        float  binwidth(bool ovr = false) const;
        DigitizedData compute(size_t, float const *) const;
    };

    /* Configure a digitizer such that the bin size, notwithstanding oversampling,
     * is *precision* beyond the HF noise in the data.
     */
    struct CyclesDigitization
    {
        size_t oversampling = 5;

        /* ratio to apply to the provided HF noise*/
        float  precision    = 1.0f/3.0f;

        /* percentile value for finding the min edge */
        float  minv         = 1.0f;
        /* percentile value for finding the max edge */
        float  maxv         = 99.0f;

        /* factor to apply to the provided HF noise guiding the edge extension */
        float  overshoot    = 5.0f;
        Digitizer compute (float, cycles_t const &) const;
    };

    /* Projects *digitized* data from a single cycle to a histogram with
     * normalized peak heights.
     *
     * Normalized peak heights means that a hybridization duration don't affect
     * the peak heights too much.
     */
    struct CycleProjection
    {
        enum struct DzPattern     { symmetric1 };
        enum struct WeightPattern { ones, inv };


        /* The filter consists in discarding values with too much of a derivative. */
        float               dzratio         = 1.0f;
        DzPattern           dzpattern       = DzPattern::symmetric1;

        /* If countratio > 0, the weight is the inverse of the number of neighbours. */
        float               countratio      = 1.0f;
        size_t              countthreshold  = 2;
        WeightPattern       weightpattern   = WeightPattern::inv;


        /* T smoothing consists in averaging over neighbouring frames */
        float               tsmoothingratio = 1.0f;
        size_t              tsmoothinglen   = 10u;

        std::vector<float>              compute(DigitizedData const &) const;
        std::vector<std::vector<float>> compute(Digitizer const &, cycles_t const &) const;
    };

    /* Projects cycle histograms to a single histogram representing
     * hybridisation rates as a function of z.
     *
     * The cycle histograms are projected using the provided z-bias.
     * Output values are normalized to the number of cycles with non-zero values
     * at the same height.
     */
    struct ProjectionAggregator
    {
        float               cycleminvalue       = 0.0f;
        float               cyclemincount       = 2.0f;
        float               zsmoothingratio     = 1.0f;
        float               countsmoothingratio = 1.0f;
        size_t              smoothinglen        = 10u;

        std::vector<float>  compute(Digitizer const &, std::vector<float const*> const &) const;
        std::vector<float>  compute(Digitizer                  const &,
                                    std::vector<int>           const &,
                                    std::vector<float const *> const &
                                   ) const;
    };

    /* Align cycles by maximizing the correlation between a consensus histogram and
     * cycle histograms.
     *
     * The maximum is found using a simple grid search.
     */
    struct CycleAlignment
    {
        float  halfwindow = 5.0f;
        size_t repeats    = 1;

        std::pair<std::vector<float>, std::vector<float>>
        compute(Digitizer                  const &,
                ProjectionAggregator       const &,
                std::vector<float const *> const &) const;
    };

    struct BeadProjection
    {
        CyclesDigitization      digitize;
        CycleProjection         project;
        ProjectionAggregator    aggregate;
        CycleAlignment          align;
        HistogramPeakFinder     find;

        BeadProjectionData      compute (float, cycles_t const &) const;
    };

    struct EventExtractor
    {
        size_t mincount = 2;
        float  density  = 1.0f;
        float  distance = 2.0f;
        std::vector<std::vector<std::pair<size_t, size_t>>>
        compute(float, size_t, float const *, float const *, cycles_t const &) const;
    };
}}
