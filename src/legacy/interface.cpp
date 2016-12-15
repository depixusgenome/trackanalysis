#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "legacy/legacyrecord.h"
#include "legacy/legacygr.h"
namespace legacy
{
    pybind11::object _readtrack(std::string name, bool notall = true)
    {
        legacy::GenRecord   rec(name);
        if((notall && rec.ncycles() <= 4) || rec.ncycles() == 0)
            return pybind11::none();

        pybind11::dict      res;

        auto cycles  = rec.cycles();
        auto first   = notall ? cycles[3*rec.nphases()]             : 0;
        auto last    = notall ? cycles[cycles.size()-rec.nphases()] : rec.nrecs();
        auto sz      = last-first;

        auto add = [&](auto key, auto val)
            {
                auto mem = val();
                res[pybind11::cast(key)] = pybind11::array(sz, mem.data()+first);
            };

        for(size_t ibead = 0, ebead = rec.nbeads(); ibead < ebead; ++ibead)
            if(notall == false || !rec.islost(ibead))
                add(ibead, [&]() { return rec.bead(ibead); });

        add("t",    [&]() { return rec.t(); });
        add("zmag", [&]() { return rec.zmag(); });
        res["nbeads"]    = pybind11::cast(rec.nbeads());
        res["cyclemin"]  = pybind11::cast((notall ?  3 : 0) + rec.cyclemin());
        res["cyclemax"]  = pybind11::cast((notall ? -1 : 0) + rec.cyclemax());
        res["ncycles"]   = pybind11::cast((notall ? -4 : 0) + rec.ncycles());
        res["nphases"]   = pybind11::cast(rec.nphases());
        res["frequency"] = pybind11::cast(rec.camerafrequency());

        std::vector<size_t> shape   = {rec.ncycles()-(notall ? 4: 0), rec.nphases()};
        std::vector<size_t> strides = {rec.nphases()*sizeof(decltype(cycles)::value_type),
                                                     sizeof(decltype(cycles)::value_type)};
        res["cycles"]          = pybind11::array(shape, strides, 
                                                 cycles.data()+(notall ? 3*rec.nphases() : 0));
        return res;
    }

    pybind11::object _readtrackrotation(std::string name)
    {
        legacy::GenRecord   rec(name);
        if(rec.ncycles() == 0)
            return pybind11::none();

        auto cycles = rec.cycles();
        auto first  = cycles[3*rec.nphases()];
        auto last   = cycles[cycles.size()-rec.nphases()];
        auto mem    = rec.rot();
        return pybind11::array(last-first, mem.data()+first);
    }

    pybind11::object _readgr(std::string name)
    {
        GrData gr(name);
        if(gr.isnone())
            return pybind11::none();
        pybind11::dict res;
        res["title"] = pybind11::cast(gr.title());

        auto get = [&](bool isx, size_t i)
                    { return pybind11::array(gr.size(isx, i), gr.data(isx, i)); };

        for(size_t i = 0; i < gr.size(); ++i)
            res[pybind11::cast(gr.title(i))] = pybind11::make_tuple(get(true, i),
                                                                    get(false, i));
        return res;
    }

    void pymodule(pybind11::module & mod)
    {
        using namespace pybind11::literals;
        mod.def("readtrack", _readtrack, "path"_a, "clipcycles"_a = true,
                "Reads a '.trk' file and returns a dictionnary of beads,\n"
                "possibly removing the first 3 cycles and the last one");
        mod.def("readtrackrotation", _readtrackrotation, "path"_a,
                "Reads a '.trk' file's rotation");
        mod.def("readgr", _readgr, "path"_a,
                "Reads a '.gr' file and returns a dictionnary of datasets");
    }
}
