#include <valarray>
#include <utility>
namespace eventdetection { namespace alignment {

    struct DataInfo
    {
        size_t        size;
        float const * data;
        size_t        ncycles;
        int   const * first;
        int   const * last;
    };
    using info_t = std::valarray<float>;

    struct ExtremumAlignment
    {
        enum Mode { min, median, max };

        size_t binsize = 15;
        Mode   mode    = min;

        info_t compute(DataInfo const &&) const;
    };

    struct PhaseEdgeAlignment
    {
        enum Mode { left, right };

        size_t window     = 15;
        Mode   mode       = left;
        double percentile = 75.;

        info_t compute(DataInfo const &&) const;
    };

    void translate      (DataInfo const &&, bool,  float *);
    void medianthreshold(DataInfo const &&, float, float *);
}}
