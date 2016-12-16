#pragma once
#include <vector>
namespace signalfilter
{
    namespace forwardbackward
    {
        struct Args
        {
            bool                    derivate   = false;
            bool                    normalize  = true;
            float                   precision  = 0.003;
            size_t                  window     = 10;
            size_t                  power      = 20;
            std::vector<size_t>     estimators = { 3,  5,  7,  9, 11, 13, 15, 17,
                                                  19, 21, 23, 25, 27, 29, 31, 33};
        };

        void run(Args const &, size_t, float *);
    }

    namespace nonlinear
    {
        struct Args
        {
            bool                    derivate   = false;
            float                   precision  = 0.003;
            size_t                  power      = 20;
            std::vector<size_t>     estimators = { 3,  5,  7,  9, 11, 13, 15, 17,
                                                  19, 21, 23, 25, 27, 29, 31, 33};
        };

        void run(Args const &, size_t, float *);
    }

    namespace clip
    {
        struct Args
        {
            float minval;
            float maxval;
        };

        void run(Args const & cf, size_t, float *);
    }
}
