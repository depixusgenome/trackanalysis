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
            std::vector<size_t>     estimators = { 3u,  5u,  7u,  9u, 11u, 13u, 15u, 17u,
                                                  19u, 21u, 23u, 25u, 27u, 29u, 31u, 33u};
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
            std::vector<size_t>     estimators = { 3u,  5u,  7u,  9u, 11u, 13u, 15u, 17u,
                                                  19u, 21u, 23u, 25u, 27u, 29u, 31u, 33u};
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
