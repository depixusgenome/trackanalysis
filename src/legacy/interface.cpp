#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "legacy/legacyrecord.h"
namespace legacy
{
    pybind11::object _open(std::string name)
    {
        legacy::GenRecord   rec(name);
        pybind11::dict      res;

        auto add = [&](auto key, auto val)
            {
                auto mem = val();
                res[pybind11::cast(key)] = pybind11::array(mem.size(), mem.data());
            };

        for(size_t ibead = 0, ebead = rec.nbeads(); ibead < ebead; ++ibead)
            add(ibead, [&]() { return rec.bead(ibead); });

        add("t", [&]() { return rec.t(); });
        add("zmag", [&]() { return rec.zmag(); });
        res["nbeads"]  = pybind11::cast(rec.nbeads());
        res["ncycles"] = pybind11::cast(rec.ncycles());
        res["nphases"] = pybind11::cast(rec.nphases());

        auto                cycles  = rec.cycles();
        std::vector<size_t> shape   = {rec.ncycles(), 2};
        std::vector<size_t> strides = {2*sizeof(decltype(cycles)::value_type),
                                         sizeof(decltype(cycles)::value_type)};
        res["cycles"]          = pybind11::array(shape, strides, cycles.data());
        res["camerafrequency"] = pybind11::cast(rec.camerafrequency());
        return res;
    };

    void pymodule(pybind11::module & mod)
    {
        mod.def("readtrack", _open, "reads a trackfile and returns a dictionnary of beads");
    }
}
