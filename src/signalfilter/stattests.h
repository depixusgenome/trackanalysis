#pragma once
#include <utility>

namespace samples
{
    namespace normal
    {
        struct Input
        {
            size_t count;
            float mean;
            float sigma;
        };

        namespace knownsigma
        {
            float value    (bool, Input const &, Input const &);
            float threshold(bool, float, float);
            float threshold(bool, float, float, size_t, size_t);
            bool  isequal  (float, float, Input const &, Input const &);
        }

        namespace homoscedastic
        {
            std::pair<size_t, float> value(Input const &, Input const &);
            bool isequal  (float, Input const &, Input const &);
            bool islower  (float, Input const &, Input const &);
            bool isgreater(float, Input const &, Input const &);
        }

        namespace heteroscedastic
        {
            std::pair<float, float> value(Input const &, Input const &);
            bool isequal  (float, Input const &, Input const &);
            bool islower  (float, Input const &, Input const &);
            bool isgreater(float, Input const &, Input const &);
        }
    }
}
