#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "legacy/legacyrecord.h"
namespace legacy
{
    pybind11::object _open(std::string name, bool notall = true)
    {
        legacy::GenRecord   rec(name);
        pybind11::dict      res;

        auto cycles  = rec.cycles();
        auto first   = notall ? cycles[3*rec.nphases()] : 0;
        auto last    = cycles[cycles.size()-rec.nphases()];
        auto sz      = notall ? last-first : rec.nrecs();

        auto add = [&](auto key, auto val)
            {
                auto mem = val();
                res[pybind11::cast(key)] = pybind11::array(sz, mem.data()+first);
            };

        for(size_t ibead = 0, ebead = rec.nbeads(); ibead < ebead; ++ibead)
            add(ibead, [&]() { return rec.bead(ibead); });

        add("t",    [&]() { return rec.t(); });
        add("zmag", [&]() { return rec.zmag(); });
        res["nbeads"]   = pybind11::cast(rec.nbeads());
        res["cyclemin"] = pybind11::cast((notall ?  3 : 0) + rec.cyclemin());
        res["cyclemax"] = pybind11::cast((notall ? -1 : 0) + rec.cyclemax());
        res["ncycles"]  = pybind11::cast((notall ? -4 : 0) + rec.ncycles());
        res["nphases"]  = pybind11::cast(rec.nphases());
        res["camerafrequency"] = pybind11::cast(rec.camerafrequency());

        std::vector<size_t> shape   = {rec.ncycles()-(notall ? 4: 0), rec.nphases()};
        std::vector<size_t> strides = {rec.nphases()*sizeof(decltype(cycles)::value_type),
                                                     sizeof(decltype(cycles)::value_type)};
        res["cycles"]          = pybind11::array(shape, strides, 
                                                 cycles.data()+(notall ? 3*rec.nphases() : 0));
        return res;
    };

    void pymodule(pybind11::module & mod)
    {
        using namespace pybind11::literals;
        mod.def("readtrack", _open, "path"_a, "clipcycles"_a = true,
                "Reads a trackfile and returns a dictionnary of beads,\n"
                "possibly removing the first 3 cycles and the last one");
    }
}
