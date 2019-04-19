#include <cstdio>
#include <fstream>
#include <algorithm>
#include "utils/pybind11.hpp"
#include "legacy/legacyrecord.h"
#include "legacy/legacygr.h"
namespace legacy
{
    namespace
    {
        template <typename T, typename K>
        pybind11::object _toimage(K & shape, T const * ptr)
        {
            auto out = pybind11::array_t<T>(shape, {long(shape[1]*sizeof(T)), long(sizeof(T))});
            std::copy(ptr, ptr+shape[1]*shape[0], out.mutable_data());
            return std::move(out);
        }

        template <typename T>
        pybind11::object _toarray(size_t sz, T const *ptr)
        {
            auto out = pybind11::array_t<T>(sz);
            std::copy(ptr, ptr+sz, out.mutable_data());
            return std::move(out);
        }

        template <typename T>
        pybind11::object _toarray(std::vector<T> const && ptr)
        { return _toarray(ptr.size(), ptr.data()); }

        void _open(legacy::GenRecord & rec, std::string name)
        {
            try
            {
                pybind11::gil_scoped_release lock;
                rec.open(name);
            }
            catch(TrackIOException const & exc)
            {
                PyErr_SetString(PyExc_IOError, exc.what());
                throw pybind11::error_already_set();
            }
        }
    }
    pybind11::object _readim(std::string name, bool all = true);

    pybind11::object _instrumenttype(std::string name)
    {
        std::string ext(".trk");
        if((name.size() > 4)
            && std::equal(name.begin()+name.size()-4, name.end(), ext.begin()))
        {
            std::ifstream stream(name, std::ios_base::in|std::ios_base::binary);
            std::string line;
            const std::string find("-src \"equally spaced reference profile");
            for(int i = 0; i < 10000 && std::getline(stream, line); ++i)
                if(std::equal(find.begin(), find.end(), line.begin()))
                    return pybind11::str("picotwist");
            return pybind11::str("sdi");
        }
        return pybind11::none();
    }

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
                res = _toimage<float>(shape, (float const *) ptr);
            else if(dt == 256)
                res = _toimage<unsigned char>(shape, (unsigned char const *) ptr);
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

        auto add = [&](auto key, auto && val)
                    { 
                        auto mem = val();
                        res[pybind11::cast(key)] = _toarray(sz, mem.data()+first);
                    };

        int axis = tpe.size() == 0 || tpe[0] == 'Z' || tpe[0] == 'z' ? 0 :
                                      tpe[0] == 'X' || tpe[0] == 'x' ? 1 :
                                      tpe[0] == 'Y' || tpe[0] == 'y' ? 2 : 3;
        if(axis == 3 && tpe.size() >= 1)
            axis = tpe[1] == '1' ? 3 : tpe[1] == '2' ? 4 : 5;

        auto calibpos = rec.pos();
        for(size_t ibead = size_t(0), ebead = rec.nbeads(); ibead < ebead; ++ibead)
            if((notall == false || !rec.islost(int(ibead)))
                && (calibpos.find((int) ibead) != calibpos.end()))
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

        auto addpairs = [](std::vector<std::pair<int, float>> const && data)
            {
                std::vector<int>   ts(data.size());
                std::vector<float> ys(data.size());
                for(int i = 0, e = int(data.size()); i < e; ++i)
                {
                    ts[i] = data[i].first;
                    ys[i] = data[i].second;
                }

                return pybind11::make_tuple(_toarray(std::move(ts)),
                                            _toarray(std::move(ys)));
            };
        
        auto temp      = rec.temperatures();
        res["Tservo"]  = addpairs(std::move(temp[0]));
        res["Tsample"] = addpairs(std::move(temp[1]));
        res["Tsink"]   = addpairs(std::move(temp[2]));
        auto vcap      = rec.vcap();
        res["vcap"]    = pybind11::make_tuple(_toarray(std::move(vcap[0])),
                                              _toarray(std::move(vcap[1])),
                                              _toarray(std::move(vcap[2])));

        pybind11::dict calib;
        pybind11::dict pos;
        char tmpname[L_tmpnam];

        std::string fname = std::tmpnam(tmpname);
        auto        sdi   = rec.sdi();
        for(auto const & val: calibpos)
        {
            pos[pybind11::int_(val.first)] = pybind11::make_tuple(std::get<0>(val.second),
                                                                  std::get<1>(val.second),
                                                                  std::get<2>(val.second));
            if(!sdi)
            {
                rec.readcalib(val.first, fname);
                calib[pybind11::int_(val.first)] = _readim(fname, false);
            }
        }

        if(!sdi)
            res["calibrations"] = calib;
        res["positions"] = pos;
        res["instrument"] = pybind11::dict();
        res["instrument"]["type"] = pybind11::str(sdi ? "sdi":"picotwist");
        res["instrument"]["name"] = rec.instrumentname();

        auto dim = rec.dimensions();
        res["dimensions"] = pybind11::make_tuple(pybind11::make_tuple(std::get<0>(dim),
                                                                      std::get<1>(dim)),
                                                 pybind11::make_tuple(std::get<2>(dim),
                                                                      std::get<3>(dim)));

        std::vector<size_t> shape   = {rec.ncycles()-(notall ? 4: 0), rec.nphases()};
        res["phases"] = _toimage<typename decltype(cycles)::value_type>
                            (shape, cycles.data()+(notall ? 3*rec.nphases() : 0));
        return std::move(res);
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
        return _toarray(last-first, mem.data()+first);
    }

    pybind11::object _readgr(std::string name)
    {
        GrData gr(name);
        if(gr.isnone())
            return pybind11::none();
        pybind11::dict res;
        res["title"] = pybind11::bytes(gr.title());

        auto get = [&](bool isx, size_t i)
                    { return _toarray(gr.size(isx, i), gr.data(isx, i)); };

        for(size_t i = 0; i < gr.size(); ++i)
            res[pybind11::bytes(gr.title(i))] = pybind11::make_tuple(get(true, i),
                                                                    get(false, i));
        return std::move(res);
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
        if(gr.isfloat())
        {
            std::vector<float> dt(dims.first*dims.second);
            gr.data((void*)dt.data());
            if(!all)
                return _toimage<float>(shape, dt.data());
            res["image"] = _toimage<float>(shape, dt.data());
        }
        else if(gr.ischar())
        {
            std::vector<unsigned char> dt(dims.first*dims.second);
            gr.data((void*)dt.data());
            if(!all)
                return _toimage<unsigned char>(shape, dt.data());
            res["image"] = _toimage<unsigned char>(shape, dt.data());
        }
        if(!all)
            return pybind11::none();
        return std::move(res);
    }

    void pymodule(pybind11::module & mod)
    {
        using namespace pybind11::literals;
        mod.def("instrumenttype", _instrumenttype, "path"_a,
                "Whether a '.trk' file was created using a picotwist or an SDI.\n"
                "\n\nThis is found by checking for calibration images in the first\n"
                "10'000 lines of the file");
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
