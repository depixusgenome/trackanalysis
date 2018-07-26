#pragma  once
#include <vector>
#include <utility>

namespace cleaning { namespace beadsubtraction {

using data_t = std::tuple<float const *, size_t>;
std::vector<float> mediansignal(std::vector<data_t> const &, size_t, size_t);
std::vector<float> meansignal  (std::vector<data_t> const &, size_t, size_t);
std::vector<float> stddevsignal(std::vector<data_t> const &, size_t, size_t);

}}
