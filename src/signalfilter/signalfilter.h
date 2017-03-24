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
            float                   precision  = 0.003f;
            size_t                  window     = 10u;
            size_t                  power      = 20u;
            std::vector<size_t>     estimators = { 1u,  5u,  15u };
        };

        void run(Args const &, size_t, float *);
    }

    namespace nonlinear
    {
        struct Args
        {
            bool                    derivate   = false;
            float                   precision  = 0.003f;
            size_t                  power      = 20u;
            std::vector<size_t>     estimators = { 1u,  5u,  15u };
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
