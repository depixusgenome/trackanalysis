#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "peakcalling/costfunction.h"
#include "peakcalling/listmatching.h"
namespace peakcalling
{
    namespace cost
    {
        namespace
        {
            pybind11::object _terms(float a, float b, float c,
                                    float const * bead1, float const * weight1, size_t size1,
                                    float const * bead2, float const * weight2, size_t size2)
            {
                auto res = terms(a, b, c,
                                 bead1, weight1, size1,
                                 bead2, weight2, size2);

                std::vector<size_t> shape   = {3, 3};
                std::vector<size_t> strides = {3*sizeof(float), sizeof(float)};

                float dt[9] =
                    { std::get<0>(std::get<0>(res)), std::get<0>(std::get<1>(res)), 0.,
                      std::get<1>(std::get<0>(res)), 0., 0.,
                      std::get<2>(std::get<0>(res)),
                      std::get<2>(std::get<1>(res)),
                      std::get<2>(std::get<2>(res)),
                    };
                return pybind11::array(shape, strides, dt);
            }
        }

        void pymodule(pybind11::module & mod)
        {
            using namespace pybind11::literals;

            auto ht = mod.def_submodule("cost");
            ht.def("compute", [](pybind11::array_t<float> const & bead1,
                                 pybind11::array_t<float> const & bead2,
                                 bool a, float b, float c, float d, float e, float f)
                    {
                        Parameters cf;
                        cf.symmetric    = a;
                        cf.sigma        = b;
                        cf.current      = {c, d};
                        cf.baseline     = e;
                        cf.singlestrand = f;
                        return compute(cf,
                                       bead1.data(), nullptr, bead1.size(),
                                       bead2.data(), nullptr, bead2.size());
                    },
                    "input1"_a,          "input2"_a,
                    "symmetry"_a = true, "noise"_a        = 0.003f,
                    "stretch"_a  = 1.f,  "bias"_a         = 0.f,
                    "baseline"_a = 0.f,  "singlestrand"_a = 0.f,
                    "Computes the cost for given parameters.\n"
                    "Returns a tuple (value, stretch gradient, bias gradient)"
                    );

            ht.def("compute", [](pybind11::array_t<float> const & bead1,
                                 pybind11::array_t<float> const & weight1,
                                 pybind11::array_t<float> const & bead2,
                                 pybind11::array_t<float> const & weight2,
                                 bool a, float b, float c, float d, float e, float f)
                    {
                        if(bead1.size() != weight1.size())
                            throw pybind11::index_error("bead1.size != weight1.size");
                        if(bead2.size() != weight2.size())
                            throw pybind11::index_error("bead2.size != weight2.size");
                        Parameters cf;
                        cf.symmetric    = a;
                        cf.sigma        = b;
                        cf.current      = {c, d};
                        cf.baseline     = e;
                        cf.singlestrand = f;
                        return compute(cf,
                                       bead1.data(), weight1.data(), bead1.size(),
                                       bead2.data(), weight2.data(), bead2.size());
                    },
                    "input1"_a,          "input2"_a,
                    "weight1"_a,         "weight2"_a,
                    "symmetry"_a = true, "noise"_a        = 0.003f,
                    "stretch"_a  = 1.f,  "bias"_a         = 0.f,
                    "baseline"_a = 0.f,  "singlestrand"_a = 0.f,
                    "Computes the cost for given parameters.\n"
                    "Returns a tuple (value, stretch gradient, bias gradient)"
                    );

            ht.def("terms", [](pybind11::array_t<float> const & bead1,
                               pybind11::array_t<float> const & bead2,
                               float a, float b, float c)
                    {
                        return _terms(a, b, c,
                                      bead1.data(), nullptr, bead1.size(),
                                      bead2.data(), nullptr, bead2.size());
                    },
                    "input1"_a,          "input2"_a,
                    "stretch"_a  = 1.f,  "bias"_a  = 0.f,
                    "noise"_a = 0.003f,
                    "Computes the cost terms for given parameters.\n"
                    );

            ht.def("terms", [](pybind11::array_t<float> const & bead1,
                               pybind11::array_t<float> const & weight1,
                               pybind11::array_t<float> const & bead2,
                               pybind11::array_t<float> const & weight2,
                               float a, float b, float c)
                    {
                        if(bead1.size() != weight1.size())
                            throw pybind11::index_error("bead1.size != weight1.size");
                        if(bead2.size() != weight2.size())
                            throw pybind11::index_error("bead2.size != weight2.size");
                        return _terms(a, b, c,
                                      bead1.data(), weight1.data(), bead1.size(),
                                      bead2.data(), weight2.data(), bead2.size());
                    },
                    "input1"_a,          "input2"_a,
                    "weight1"_a,          "weight2"_a,
                    "stretch"_a  = 1.f,  "bias"_a  = 0.f,
                    "noise"_a = 0.003f,
                    "Computes the cost terms for given parameters.\n"
                    );


            ht.def("optimize", [](pybind11::array_t<float> const & bead1,
                                  pybind11::array_t<float> const & bead2,
                                  bool   sym,  float sig,
                                  float  ls,   float cs, float us,
                                  float  lb,   float cb, float ub,
                                  float  basl, float sstrand,
                                  double rpar, double apar, double rfcn, double stop,
                                  size_t maxe)
                    {
                        Parameters cf;
                        cf.symmetric    = sym;
                        cf.sigma        = sig;
                        cf.current      = {cs, cb};
                        cf.lower        = {ls, lb};
                        cf.upper        = {us, ub};
                        cf.xrel         = rpar;
                        cf.frel         = rfcn;
                        cf.xabs         = apar;
                        cf.stopval      = stop;
                        cf.maxeval      = maxe;
                        cf.baseline     = basl;
                        cf.singlestrand = sstrand;
                        return optimize(cf,
                                        bead1.data(), nullptr, bead1.size(),
                                        bead2.data(), nullptr, bead2.size());
                    },
                    "input1"_a,                "input2"_a,
                    "symmetry"_a    = true,    "noise"_a   = 0.003f,
                    "min_stretch"_a = 0.8f,    "stretch"_a = 1.f, "max_stretch"_a = 1.2f,
                    "min_bias"_a    = -0.005f, "bias"_a    = 0.f, "max_bias"_a    = .005f,
                    "baseline"_a    = 0.f,     "singlestrand"_a = 0.f,
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
                                  float  basl, float sstrand,
                                  double rpar, double apar, double rfcn, double stop,
                                  size_t maxe
                                 )
                    {
                        if(bead1.size() != weight1.size())
                            throw pybind11::index_error("bead1.size != weight1.size");
                        if(bead2.size() != weight2.size())
                            throw pybind11::index_error("bead2.size != weight2.size");
                        Parameters cf;
                        cf.symmetric    = sym;
                        cf.sigma        = sig;
                        cf.current      = {cs, cb};
                        cf.lower        = {ls, lb};
                        cf.upper        = {us, ub};
                        cf.xrel         = rpar;
                        cf.frel         = rfcn;
                        cf.xabs         = apar;
                        cf.stopval      = stop;
                        cf.maxeval      = maxe;
                        cf.baseline     = basl;
                        cf.singlestrand = sstrand;
                        return optimize(cf,
                                        bead1.data(), weight1.data(), bead1.size(),
                                        bead2.data(), weight2.data(), bead2.size());
                    },
                    "input1"_a,                "input2"_a,
                    "weight1"_a,               "weight2"_a,
                    "symmetry"_a    = true,    "noise"_a   = 0.003f,
                    "min_stretch"_a = 0.8f,    "stretch"_a = 1.f, "max_stretch"_a = 1.2f,
                    "min_bias"_a    = -0.005f, "bias"_a    = 0.f, "max_bias"_a    = .005f,
                    "baseline"_a    = 0.f,     "singlestrand"_a = 0.f,
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
        struct Iterator
        {
            float   minstretch, maxstretch, minbias, maxbias;
            float const * ref;  size_t nref;
            float const * exp;  size_t nexp;
            size_t i1r, i2r, i1e, i2e;
            bool   index;

            pybind11::object next()
            {
                float  params [2];
                float &stretch = params[0], &bias=params[1];
                pybind11::object res;
                std::vector<size_t> shape;
                std::vector<size_t> strides;

                if(index)
                {
                    shape   = {2, 2};
                    strides = {2*sizeof(size_t), sizeof(size_t)};
                } else
                {
                    shape   = {2};
                    strides = {sizeof(float)};
                }

                while(true)
                {
                    if(i1r == nref-1)
                        throw pybind11::stop_iteration();

                    bool good = false;
                    stretch = (ref[i2r]-ref[i1r])/(exp[i2e]-exp[i1e]);
                    if(stretch > minstretch && stretch < maxstretch)
                    {
                        bias = exp[i1e] - ref[i1r]/stretch;
                        good = bias > minbias && bias < maxbias;
                    }

                    size_t inds   [4] = {i1r, i1e, i2r, i2e};
                    if(i2e == nexp-1 && i1e == nexp-2)
                    {
                        i1e = 0;
                        i2e = 1;
                        if(i2r == nref-1)
                        {
                            ++i1r;
                            i2r = i1r+1;
                        } else
                            ++i2r;
                    } else if(i2e == nexp-1)
                    {
                        ++i1e;
                        i2e = i1e+1;
                    } else
                        ++i2e;

                    if(good)
                    {
                        if(index)
                            return pybind11::array(shape, strides, inds);
                        else
                            return pybind11::array(shape, strides, params);
                    }
                }
            }
        };

        std::unique_ptr<Iterator> _init(pybind11::array_t<float> const & ref,
                                        pybind11::array_t<float> const & exp,
                                        float minstretch, float maxstretch,
                                        float minbias,    float maxbias, bool index)
        {
            auto ptr = std::unique_ptr<Iterator>(new Iterator());
            ptr->ref        = ref.data(); ptr->nref       = ref.size();
            ptr->exp        = exp.data(); ptr->nexp       = exp.size();
            ptr->minstretch = minstretch; ptr->maxstretch = maxstretch;
            ptr->minbias    = minbias;    ptr->maxbias    = maxbias;
            ptr->i1r        = 0;          ptr->i2r        = 1;
            ptr->i1e        = 0;          ptr->i2e        = 1;
            ptr->index      = index;
            return ptr;
        }

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

            pybind11::class_<Iterator> cls(ht, "PeakIterator");
            cls.def(pybind11::init(&_init),
                    "reference"_a,  "experiment"_a,
                    "minstretch"_a = .01,   "maxstretch"_a = 10.,
                    "minbias"_a    = -10.,  "maxbias"_a    = 10.,
                    "indexes"_a    = false,
                    pybind11::keep_alive<1,2>(),
                    pybind11::keep_alive<1,3>());
            cls.def("__next__", &Iterator::next);
            cls.def("__iter__", [](pybind11::object & self) { return self; });
        }
    }

    void pymodule(pybind11::module & mod)
    {
        cost::pymodule(mod);
        match::pymodule(mod);
    }
}
