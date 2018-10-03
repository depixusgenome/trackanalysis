#pragma  once
#include <vector>
#include <utility>
#include <string>

namespace cleaning { namespace beadsubtraction {

using data_t = std::tuple<float const *, size_t>;
std::vector<float> mediansignal(std::vector<data_t> const &, size_t, size_t);
std::vector<float> meansignal  (std::vector<data_t> const &, size_t, size_t);
std::vector<float> stddevsignal(std::vector<data_t> const &, size_t, size_t);

std::vector<float> phasebaseline(std::string txt,
                                 data_t signals,
                                 size_t cnt, int const * ix1,  int const * ix2);
std::vector<float> phasebaseline(std::string txt,
                                 std::vector<data_t> const & signals,
                                 size_t cnt, int const * ix1,  int const * ix2);
}}
