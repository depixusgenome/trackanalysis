#include <cstdio>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "legacy/legacyrecord.h"
#include "legacy/legacygr.h"
namespace legacy
{
    namespace
    {
        template <typename T, typename K>
        pybind11::object _toimage(K & shape, void *ptr)
        {
            std::vector<size_t> strides(2);
            strides = { shape[1]*sizeof(T), sizeof(T) };
            std::vector<T> dt(shape[1]*shape[2]);
            return pybind11::array(shape, strides, (T*) ptr);
        }

        void _open(legacy::GenRecord & rec, std::string name)
        {
            pybind11::gil_scoped_release lock;
            rec.open(name);
        }
    }
    pybind11::object _readim(std::string name, bool all = true);

    pybind11::object _readrecfov(legacy::GenRecord &rec)
    {
        int nx, ny, dt;
        void *ptr = nullptr;
        pybind11::object res = pybind11::none();
        try
        {
            rec.readfov(nx, ny, dt, ptr);
            std::vector<size_t> shape = {(size_t) ny, (size_t) nx};

            if(dt == 512)
                res = _toimage<float>(shape, ptr);
            else if(dt == 256)
                res = _toimage<unsigned char>(shape, ptr);
        } catch(...) {};

        rec.destroyfov(dt, ptr);
        return res;
    }

    pybind11::object _readfov(std::string name)
    {
        legacy::GenRecord rec;
        _open(rec, name);

        return rec.ncycles() == 0 ? pybind11::none() : _readrecfov(rec);
    }

    pybind11::object _readtrack(std::string name,
                                bool notall     = true,
                                std::string tpe = "")
    {
        legacy::GenRecord   rec;
        _open(rec, name);
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

        int axis = tpe.size() == 0 || tpe[0] == 'Z' || tpe[0] == 'z' ? 0 :
                                      tpe[0] == 'X' || tpe[0] == 'x' ? 1 : 2;

        auto calibpos = rec.pos();
        auto sdi      = rec.sdi();
            
        for(size_t ibead = size_t(0), ebead = rec.nbeads(); ibead < ebead; ++ibead)
            if((notall == false || !rec.islost(int(ibead)))
                && (sdi || calibpos.find(ibead) != calibpos.end()))
                add(ibead, [&]() { return rec.bead(ibead, axis); });

        add("t",    [&]() { return rec.t(); });
        add("zmag", [&]() { return rec.zmag(); });
        res["nbeads"]    = pybind11::cast(rec.nbeads());
        res["cyclemin"]  = pybind11::cast((notall ?  3 : 0) + rec.cyclemin());
        res["cyclemax"]  = pybind11::cast((notall ? -1 : 0) + rec.cyclemax());
        res["ncycles"]   = pybind11::cast((notall ? -4 : 0) + rec.ncycles());
        res["nphases"]   = pybind11::cast(rec.nphases());
        res["framerate"] = pybind11::cast(rec.camerafrequency());
        res["fov"]       = _readrecfov(rec);

        pybind11::dict calib;
        pybind11::dict pos;
        char tmpname[L_tmpnam];
        std::string fname = std::tmpnam(tmpname);
        for(auto const & val: calibpos)
        {
            pos[pybind11::int_(val.first)] = pybind11::make_tuple(std::get<0>(val.second),
                                                                  std::get<1>(val.second),
                                                                  std::get<2>(val.second));
            rec.readcalib(val.first, fname);
            calib[pybind11::int_(val.first)] = _readim(fname, false);
        }

        res["calibrations"] = calib;
        res["positions"] = pos;

        auto dim = rec.dimensions();
        res["dimensions"] = pybind11::make_tuple(pybind11::make_tuple(std::get<0>(dim),
                                                                      std::get<1>(dim)),
                                                 pybind11::make_tuple(std::get<2>(dim),
                                                                      std::get<3>(dim)));

        std::vector<size_t> shape   = {rec.ncycles()-(notall ? 4: 0), rec.nphases()};
        std::vector<size_t> strides = {rec.nphases()*sizeof(decltype(cycles)::value_type),
                                                     sizeof(decltype(cycles)::value_type)};
        res["phases"]    = pybind11::array(shape, strides,
                                           cycles.data()+(notall ? 3*rec.nphases() : 0));
        return res;
    }

    pybind11::object _readtrackrotation(std::string name)
    {
        legacy::GenRecord   rec;
        _open(rec, name);
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
        res["title"] = pybind11::bytes(gr.title());

        auto get = [&](bool isx, size_t i)
                    { return pybind11::array(gr.size(isx, i), gr.data(isx, i)); };

        for(size_t i = 0; i < gr.size(); ++i)
            res[pybind11::bytes(gr.title(i))] = pybind11::make_tuple(get(true, i),
                                                                    get(false, i));
        return res;
    }

    pybind11::object _readim(std::string name, bool all)
    {
        ImData gr(name);
        if(gr.isnone())
            return pybind11::none();
        pybind11::dict res;
        res["title"] = pybind11::bytes(gr.title());

        auto dims = gr.dims();

        std::vector<size_t> shape   = {dims.second, dims.first };
        std::vector<size_t> strides(2);
        if(gr.isfloat())
        {
            strides = { dims.first*sizeof(float), sizeof(float) };
            std::vector<float> dt(dims.first*dims.second);
            gr.data((void*)dt.data());
            if(!all)
                return pybind11::array(shape, strides, dt.data());
            res["image"] = pybind11::array(shape, strides, dt.data());
        }
        else if(gr.ischar())
        {
            strides = { dims.first*sizeof(char), sizeof(char) };
            std::vector<unsigned char> dt(dims.first*dims.second);
            gr.data((void*)dt.data());
            if(!all)
                return pybind11::array(shape, strides, dt.data());
            res["image"] = pybind11::array(shape, strides, dt.data());
        }
        if(!all)
            return pybind11::none();
        return res;
    }

    void pymodule(pybind11::module & mod)
    {
        using namespace pybind11::literals;
        mod.def("readtrack", _readtrack, "path"_a,
                "clipcycles"_a = true, "axis"_a = "z",
                "Reads a '.trk' file and returns a dictionnary of beads,\n"
                "possibly removing the first 3 cycles and the last one.\n"
                "axes are x, y or z");
        mod.def("readtrackrotation", _readtrackrotation, "path"_a,
                "Reads a '.trk' file's rotation");
        mod.def("readgr", _readgr, "path"_a,
                "Reads a '.gr' file and returns a dictionnary of datasets");
        mod.def("readim", _readim, "path"_a, "readall"_a = true,
                "Reads a '.gr' file and returns an image");
        mod.def("fov",    _readfov, "path"_a,
                "Reads a '.trk' file and returns the FoV image");
    }
}
