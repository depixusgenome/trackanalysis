#include "cleaning/interface/interface.h"

namespace cleaning::beadsubtraction {
#   define DPX_INIT_RED                                                         \
        if(pydata.size() == 0)                                                  \
            return ndarray<float>(0);                                           \
                                                                                \
        if(pydata.size() == 1)                                                  \
            return toarray(pydata[0]);                                          \
                                                                                \
        std::vector<data_t> data;                                               \
        for(auto const & i: pydata)                                             \
            data.emplace_back(i.data(), i.size());                              \
                                                                                \
        size_t total = 0u;                                                      \
        for(auto const & i: data)                                               \
            total = std::max(total, std::get<1>(i));

    ndarray<float> reducesignal(std::string tpe, size_t i1, size_t i2,
                                std::vector<ndarray<float>> pydata)
    {
        DPX_INIT_RED
        return toarray(total,
                       [&]()
                       {
                           return (tpe == "median" ? mediansignal(data, i1, i2) :
                                   tpe == "stddev" ? stddevsignal(data, i1, i2) :
                                   meansignal(data, i1, i2));
                       });
    }

    ndarray<float> reducesignal2(std::string tpe,
                                 std::vector<ndarray<float>> pydata)
    { return reducesignal(tpe, 0, 0, pydata); }

    ndarray<float> reducesignal3(std::string tpe,
                                 std::vector<ndarray<float>> pydata,
                                 std::vector<ndarray<int>>   pyphase)
    {
        int const * phases[] = {pyphase[0].data(),
                                pyphase[1].data(),
                                pyphase[2].data()};
        size_t      sz       =  pyphase[0].size();

        DPX_INIT_RED
        auto pyout = toarray(total, std::numeric_limits<float>::quiet_NaN());
        auto ptr   = pyout.mutable_data();
        {
            py::gil_scoped_release _;
            for(size_t i = 0; i < sz; ++i)
            {
                auto i1(phases[0][i]);
                auto i2(phases[1][i]-i1), i3(phases[2][i]-i1);
                auto i4(i+1 < sz ? phases[0][i+1] : total);

                std::vector<data_t> tmp;
                for(auto const & i: data)
                    tmp.emplace_back(std::get<0>(i)+i1, std::min(i4,std::get<1>(i))-i1);

                auto out(tpe == "median" ? mediansignal(tmp, i2, i3) :
                         tpe == "stddev" ? stddevsignal(tmp, i2, i3) :
                         meansignal(tmp, i2, i3));
                std::copy(out.begin(), out.end(), ptr+i1);
            }
        }
        return pyout;
    }

    ndarray<float> pyphasebaseline1(std::string tpe,
                                  ndarray<float> pydata,
                                  ndarray<int>   pyi1,
                                  ndarray<int>   pyi2)
    {
        int const * i1 = pyi1.data();
        int const * i2 = pyi2.data();
        size_t      sz = pyi1.size();

        ndarray<float> pyout(sz);
        auto ptr(pyout.mutable_data());
        std::fill(ptr, ptr+sz, std::numeric_limits<float>::quiet_NaN());

        if(sz == 0)
            return pyout;

        data_t data = {pydata.data(), pydata.size()};
        {
            py::gil_scoped_release _;
            auto out = phasebaseline(tpe, data, sz, i1, i2);
            std::copy(out.begin(), out.end(), ptr);
        }
        return pyout;
    }

    ndarray<float> pyphasebaseline(std::string tpe,
                                 std::vector<ndarray<float>> pydata,
                                 ndarray<int>                pyi1,
                                 ndarray<int>                pyi2)
    {
        int const * i1 = pyi1.data();
        int const * i2 = pyi2.data();
        size_t      sz = pyi1.size();

        if(pydata.size() == 0 || sz == 0)
            return toarray(sz, std::numeric_limits<float>::quiet_NaN());

        std::vector<data_t> data;
        for(auto const & i: pydata)
            data.emplace_back(i.data(), i.size());
        return toarray(sz, [&]() { return phasebaseline(tpe, data, sz, i1, i2); });
    }

    ndarray<int>  pydzcount(float threshold,
                            ndarray<float> pydata,
                            ndarray<int>   pyi1,
                            ndarray<int>   pyi2)
    {
#       define PY_DZCOUNT_INPT(CODE)                \
        int const    * i1   = pyi1.data();          \
        int const    * i2   = pyi2.data();          \
        size_t         sz   = pyi1.size();          \
        float const  * data = pydata.data();        \
        if(pydata.size() == 0 || pyi1.size() == 0)  \
            return CODE;

        PY_DZCOUNT_INPT(toarray(sz, 0))
        return toarray(sz, [&]() { return dzcount(threshold, sz, data, i1, i2); });
    }

    size_t  pydzcount2(float dzthr,
                       ndarray<float> pydata,
                       ndarray<int>   pyi1,
                       ndarray<int>   pyi2)
    {
        PY_DZCOUNT_INPT(0u)
        return dztotalcount(dzthr, sz, data, i1, i2);
    }

    void pymodule(py::module & mod)
    {
        using namespace py::literals;
        mod.def("reducesignals", reducesignal);
        mod.def("reducesignals", reducesignal2);
        mod.def("reducesignals", reducesignal3);
        mod.def("phasebaseline", pyphasebaseline);
        mod.def("phasebaseline", pyphasebaseline1);

        auto doc = R"_(Return an array with the number of frames with to low a derivative.)_";
        mod.def("dzcount", pydzcount,  doc);
        doc = R"_(Return the number of frames with to low a derivative.)_";
        mod.def("dztotalcount", pydzcount2, doc);
    }
}
