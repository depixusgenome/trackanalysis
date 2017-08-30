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
                        Parameters cf; cf.symmetric = a; cf.sigma = b; cf.current = {c, d};
                        return compute(cf,
                                       bead1.data(), nullptr, bead1.size(),
                                       bead2.data(), nullptr, bead2.size());
                    },
                    "input1"_a,          "input2"_a,
                    "symmetry"_a = true, "noise"_a = 0.003f,
                    "stretch"_a  = 1.f,  "bias"_a  = 0.f,
                    "Computes the cost for given parameters.\n"
                    "Returns a tuple (value, stretch gradient, bias gradient)"
                    );

            ht.def("compute", [](pybind11::array_t<float> const & bead1,
                                 pybind11::array_t<float> const & weight1,
                                 pybind11::array_t<float> const & bead2,
                                 pybind11::array_t<float> const & weight2,
                                 bool a, float b, float c, float d)
                    {
                        if(bead1.size() != weight1.size())
                            throw pybind11::index_error("bead1.size != weight1.size");
                        if(bead2.size() != weight2.size())
                            throw pybind11::index_error("bead2.size != weight2.size");
                        Parameters cf; cf.symmetric = a; cf.sigma = b; cf.current = {c, d};
                        return compute(cf,
                                       bead1.data(), weight1.data(), bead1.size(),
                                       bead2.data(), weight2.data(), bead2.size());
                    },
                    "input1"_a,          "input2"_a,
                    "weight1"_a,         "weight2"_a,
                    "symmetry"_a = true, "noise"_a = 0.003f,
                    "stretch"_a  = 1.f,  "bias"_a  = 0.f,
                    "Computes the cost for given parameters.\n"
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
                        Parameters cf; cf.symmetric = sym; cf.sigma = sig; cf.current = {cs, cb};
                        cf.lower = {ls, lb}; cf.upper = {us, ub}; cf.xrel = rpar; cf.frel = rfcn;
                        cf.xabs  = apar; cf.stopval = stop; cf.maxeval = maxe;
                        return optimize(cf,
                                        bead1.data(), nullptr, bead1.size(),
                                        bead2.data(), nullptr, bead2.size());
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
                    "Optimizes the cost for given parameters."
                    "Returns a tuple (min cost, best stretch, best bias)");

            ht.def("optimize", [](pybind11::array_t<float> const & bead1,
                                  pybind11::array_t<float> const & weight1,
                                  pybind11::array_t<float> const & bead2,
                                  pybind11::array_t<float> const & weight2,
                                  bool   sym,  float sig,
                                  float  ls,   float cs, float us,
                                  float  lb,   float cb, float ub,
                                  double rpar, double apar, double rfcn, double stop,
                                  size_t maxe
                                 )
                    {
                        if(bead1.size() != weight1.size())
                            throw pybind11::index_error("bead1.size != weight1.size");
                        if(bead2.size() != weight2.size())
                            throw pybind11::index_error("bead2.size != weight2.size");
                        Parameters cf; cf.symmetric = sym; cf.sigma = sig; cf.current = {cs, cb};
                        cf.lower = {ls, lb}; cf.upper = {us, ub}; cf.xrel = rpar; cf.frel = rfcn;
                        cf.xabs  = apar; cf.stopval = stop; cf.maxeval = maxe;
                        return optimize(cf,
                                        bead1.data(), weight1.data(), bead1.size(),
                                        bead2.data(), weight2.data(), bead2.size());
                    },
                    "input1"_a,                "input2"_a,
                    "weight1"_a,               "weight2"_a,
                    "symmetry"_a    = true,    "noise"_a   = 0.003f,
                    "min_stretch"_a = 0.8f,    "stretch"_a = 1.f, "max_stretch"_a = 1.2f,
                    "min_bias"_a    = -0.005f, "bias"_a    = 0.f, "max_bias"_a    = .005f,
                    "threshold_param_rel"_a = 1e-4,
                    "threshold_param_abs"_a = 1e-8,
                    "threshold_func_rel"_a  = 1e-4,
                    "stopval"_a             = 1e-8,
                    "maxeval"_a             = size_t(100),
                    "Optimizes the cost for given parameters."
                    "Returns a tuple (min cost, best stretch, best bias)");
        }
    }

    namespace match
    {
        void pymodule(pybind11::module & mod)
        {
            using namespace pybind11::literals;

            auto ht = mod.def_submodule("match");
            ht.def("compute", [](pybind11::array_t<float> const & bead1,
                                 pybind11::array_t<float> const & bead2,
                                 float s)
                    {
                        auto ret = compute(s, bead1.data(), bead1.size(),
                                              bead2.data(), bead2.size());

                        std::vector<size_t> shape   = {ret.size()/2, 2};
                        std::vector<size_t> strides = {2*sizeof(decltype(ret[0])),
                                                         sizeof(decltype(ret[0])) };
                        return pybind11::array(shape, strides, ret.data());
                    },
                    "reference"_a,   "experiment"_a, "sigma"_a = 20.,
                    "Matches peaks from the experiment to the reference,\n"
                    "allowing a maximum distance of *sigma*.\n\n"
                    "Output is a array of indexes");

            ht.def("nfound", [](pybind11::array_t<float> const & bead1,
                                pybind11::array_t<float> const & bead2,
                                float s)
                    {
                        return nfound(s, bead1.data(), bead1.size(),
                                         bead2.data(), bead2.size());
                    },
                    "reference"_a,   "experiment"_a, "sigma"_a = 20.,
                    "Counts the number of matched peaks,\n"
                    "allowing a maximum distance of *sigma* to a match.\n\n"
                    "Output is a positive integer");

            ht.def("distance", [](pybind11::array_t<float> const & bead1,
                                  pybind11::array_t<float> const & bead2,
                                  float s, float stretch, float bias)
                    {
                        return distance(s, stretch, bias,
                                        bead1.data(), bead1.size(),
                                        bead2.data(), bead2.size());
                    },
                    "reference"_a,   "experiment"_a, "sigma"_a = 20.,
                    "stretch"_a = 1., "bias"_a = 0.,
                    "Computes the square of the distance between matched peaks,"
                    "allowing a maximum distance of *sigma* to a match.\n\n"
                    "Outputs a tuple with:\n\n"
                    "    1. Σ_{paired} (x_i - y_i)² / (σ² N) +"
                        " len(reference)+len(experiment) - 2N\n"
                    "    2. stretch gradient\n"
                    "    3. bias gradient\n"
                    "    4. N: number of paired peaks\n");

            ht.def("optimize", [](pybind11::array_t<float> const & bead1,
                                  pybind11::array_t<float> const & bead2,
                                  float sig,
                                  float  ls,   float cs, float us,
                                  float  lb,   float cb, float ub,
                                  double rpar, double apar, double rfcn, double stop,
                                  size_t maxe
                                 )
                    {
                        Parameters cf; cf.sigma = sig; cf.current = {cs, cb};
                        cf.lower = {ls, lb}; cf.upper = {us, ub}; cf.xrel = rpar; cf.frel = rfcn;
                        cf.xabs  = apar; cf.stopval = stop; cf.maxeval = maxe;
                        return optimize(cf,
                                        bead1.data(), bead1.size(),
                                        bead2.data(), bead2.size());
                    },
                    "reference"_a,           "experiment"_a,
                    "window"_a      = 10.0,
                    "min_stretch"_a = 0.8f,    "stretch"_a = 1.f, "max_stretch"_a = 1.2f,
                    "min_bias"_a    = -0.005f, "bias"_a    = 0.f, "max_bias"_a    = .005f,
                    "threshold_param_rel"_a = 1e-4,
                    "threshold_param_abs"_a = 1e-8,
                    "threshold_func_rel"_a  = 1e-4,
                    "stopval"_a             = 1e-8,
                    "maxeval"_a             = size_t(100),
                    "Optimizes the distance for given parameters."
                    "Returns a tuple (min cost, best stretch, best bias)");
        }
    }


    void pymodule(pybind11::module & mod)
    {
        cost::pymodule(mod);
        match::pymodule(mod);
    }
}
