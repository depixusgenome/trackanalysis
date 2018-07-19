#pragma once
namespace cleaning {
    template <typename T>
    struct ConstantValuesSuppressor
    {
        T      mindeltavalue = T(1e-6);
        size_t mindeltarange = 3;

        void apply(size_t, T *) const;
    };

    extern template struct ConstantValuesSuppressor<float>;
    extern template struct ConstantValuesSuppressor<double>;

    template <typename T>
    struct DerivateSuppressor
    {
        T maxabsvalue = T(5.);
        T maxderivate = T(.6);

        void apply(size_t, T *, bool, double) const;
    };

    extern template struct DerivateSuppressor<float>;
    extern template struct DerivateSuppressor<double>;

    /* Removes frames which have NaN values to their right and their left */
    struct LocalNaNPopulation
    {
        size_t window = 5;
        size_t ratio  = 20;

        void apply(size_t, float *) const;
    };

    /*
    Removes frame intervals with the following characteristics:

    * there are *islandwidth* or less good values in a row,
    * with a derivate of at least *maxderivate*
    * surrounded by *riverwidth* or more NaN values in a row on both sides
    */
    struct NaNDerivateIslands
    {
        size_t riverwidth  = 2;
        size_t islandwidth = 10;
        size_t ratio       = 80;
        double  maxderivate = .02;

        void apply(size_t, float *) const;
    };

    /*
    Removes aberrant values.

    A value at position *n* is aberrant if any:

    * |z[n] - median(z)| > maxabsvalue
    * |(z[n+1]-z[n-1])/2-z[n]| > maxderivate
    * |z[I-mindeltarange+1] - z[I-mindeltarange+2] | < mindeltavalue
      && ...
      && |z[I-mindeltarange+1] - z[I]|               < mindeltavalue
      && n ∈ [I-mindeltarange+2, I]
    * #{z[I-nanwindow//2:I+nanwindow//2] is nan} < nanratio*nanwindow
    */
    struct AberrantValuesRule
    {
        ConstantValuesSuppressor<float> constants;
        DerivateSuppressor<float>       derivative;
        LocalNaNPopulation              localnans;
        NaNDerivateIslands              islands;

        void apply(size_t, float *, bool = false) const;
    };

    struct DataInfo
    {
        size_t              nframes;
        float       const * data;

        size_t              ncycles;
        long long   const * start;
        long long   const * stop;
    };

    struct DataOutput
    {
        DataOutput(size_t ncycles);
        std::vector<float> values;
        std::vector<int>   minv;
        std::vector<int>   maxv;
    };

    struct HFSigmaRule
    {
        DataOutput apply(DataInfo info) const;
        double minv = 1e-4;
        double maxv = 1e-2;
    };

    struct PopulationRule
    {
        DataOutput apply(DataInfo info) const;
        double minv = 80.0;
    };

    struct ExtentRule
    {
        DataOutput apply(DataInfo info) const;
        double minv          = .25;
        double maxv          = 2.0;
        double minpercentile = 5.0;
        double maxpercentile = 95.0;
    };

    struct PingPongRule
    {
        DataOutput apply(DataInfo info) const;
        double maxv          = 3.0;
        double mindifference = .01;
        double minpercentile = 5.;
        double maxpercentile = 95.;
    };

    struct SaturationRule
    {
        DataOutput apply(DataInfo initial, DataInfo measures) const;
        double  maxv          = 20.0;
        double  maxdisttozero = .015;
        size_t  satwindow     = 10;
    };
}
