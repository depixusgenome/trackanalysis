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

        void apply(size_t, T *, bool, float) const;
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
        float  maxderivate = .02;

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
}
