#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "peakcalling/costfunction.h"
#include "peakcalling/listmatching.h"
namespace peakcalling
{
    namespace cost
    {
        void pymodule(pybind11::module & mod)
        {
            using namespace pybind11::literals;

            auto ht = mod.def_submodule("cost");
            ht.def("compute", [](pybind11::array_t<float> const & bead1,
                                 pybind11::array_t<float> const & bead2,
                                 bool a, float b, float c, float d)
                    {
                        return compute({a, b, c, d},
                                       bead1.data(), bead1.size(),
                                       bead2.data(), bead2.size());
                    },
                    "input1"_a,          "input2"_a,
                    "symmetry"_a = true, "noise"_a = 0.003f,
                    "stretch"_a  = 1.f,  "bias"_a  = 0.f,
                    "Computes the cost function value for given parameters.\n"
                    "Returns a tuple (value, stretch gradient, bias gradient)"
                    );

            ht.def("optimize", [](pybind11::array_t<float> const & bead1,
                                  pybind11::array_t<float> const & bead2,
                                  bool   sym,  float sig,
                                  float  ls,   float cs, float us,
                                  float  lb,   float cb, float ub,
                                  double rpar, double apar, double rfcn, double stop,
                                  size_t maxe
                                 )
                    {
                        return optimize({ sym, sig,
                                         {bead1.data(), bead2.data()},
                                         {bead1.size(), bead2.size()},
                                         {ls, lb}, {cs, cb}, {us, ub},
                                         rpar, rfcn, apar, stop, maxe});
                    },
                    "input1"_a,                "input2"_a,
                    "symmetry"_a    = true,    "noise"_a   = 0.003f,
                    "min_stretch"_a = 0.8f,    "stretch"_a = 1.f, "max_stretch"_a = 1.2f,
                    "min_bias"_a    = -0.005f, "bias"_a    = 0.f, "max_bias"_a    = .005f,
                    "threshold_param_rel"_a = 1e-4,
                    "threshold_param_abs"_a = 1e-8,
                    "threshold_func_rel"_a  = 1e-4,
                    "stopval"_a             = 1e-8,
                    "maxeval"_a             = size_t(100),
                    "Optimizes the cost function value for given parameters."
                    "Returns a tuple (min cost, best stretch, best bias)");
        }
    }

    namespace match
    {
        void pymodule(pybind11::module & mod)
        {
            using namespace pybind11::literals;

            auto ht = mod.def_submodule("match");
            ht.def("compute", [](pybind11::array_t<float> & bead1,
                                 pybind11::array_t<float> & bead2,
                                 float s)
                    {
                        auto b1  = bead1.request();
                        auto b2  = bead2.request();
                        auto ret = compute(s,
                                       (float const*) b1.ptr, b1.size,
                                       (float const*) b2.ptr, b2.size);

                        std::vector<size_t> shape   = {ret.size(), 2};
                        std::vector<size_t> strides = {2*sizeof(int), sizeof(int) };
                        return pybind11::array(shape, strides, ret.data());
                    },
                    "reference"_a,   "experiment"_a, "sigma"_a = 20.,
                    "Matches peaks from the experiment to the reference, with a\n"
                    "max distance of *sigma*.\n\n"
                    "Output is a array of indexes");
        }
    }


    void pymodule(pybind11::module & mod)
    {
        cost::pymodule(mod);
        match::pymodule(mod);
    }
}
