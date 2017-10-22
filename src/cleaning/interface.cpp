#include <cmath>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

namespace cleaning {
    template <typename T>
    using ndarray = pybind11::array_t<T, pybind11::array::c_style>;

    template <typename T>
    void constant(pybind11::object const & self, ndarray<T> & pydata)
    {
        auto    minrange = self.attr("mindeltarange").cast<int>();
        auto    mindelta = self.attr("mindeltavalue").cast<T>();
        T     * data     = pydata.mutable_data();
        int i = 1, j = 0;
        auto    check    = [&]()
                            {
                                if(j+minrange <= i)
                                    for(int k = j+1; k < i; ++k)
                                        data[k] = NAN;
                            };
        for(int e = int(pydata.size()); i < e; ++i)
        {
            if(std::isnan(data[i]) || std::abs(data[i]-data[j]) < mindelta)
                continue;

            check();
            j = i;
        }

        check();
    }

    template <typename T>
    void clip(pybind11::object const & self, bool doclip, float azero, ndarray<T> & pydata)
    {
        int     e      = int(pydata.size());
        T     * data   = pydata.mutable_data();
        auto    maxval = self.attr("maxabsvalue").cast<T>();
        T       zero   = T(azero);
        if(!doclip)
        {
            auto  maxder = self.attr("maxderivate").cast<T>();
            int i1 = 0;
            for(; i1 < e && std::isnan(data[i1]); ++i1)
                ;

            if(i1 < e)
            {

                T d0 = data[i1];
                T d1 = data[i1];
                for(int i2  = i1+1; i2 < e; ++i2)
                {
                    if(std::isnan(data[i2]))
                        continue;

                    if(std::abs(d1-zero) > maxval || std::abs(d1-.5*(d0+data[i2])) > maxder)
                        data[i1] = NAN;

                    d0 = d1;
                    d1 = data[i2];
                    i1 = i2;
                }

                if(std::abs(d1-zero) > maxval || std::abs(.5*(d1-d0)) < maxder)
                    data[i1] = NAN;
            }
        } else
        {
            T const high = zero+maxval;
            T const low  = zero-maxval;
            for(int i = 0; i < e; ++i)
            {
                if(std::isnan(data[i]))
                    continue;
                if(data[i] > maxval + zero)
                    data[i] = high;
                else if(data[i] < zero - maxval)
                    data[i] = low;
            }
        }
    }

    void pymodule(pybind11::module & mod)
    {
        using namespace pybind11::literals;
        char * doccst = "Removes constant values.\n"
                        "* |z[I-mindeltarange+1] - z[I-mindeltarange+2] | < mindeltavalue\n"
                        "*  & ...\n"
                        "*  & |z[I-mindeltarange+1] - z[I]|              < mindeltavalue\n"
                        "*  & n ∈ [I-mindeltarange+2, I]\n";
        mod.def("constant", constant<float>,  "datacleaningobject"_a, "array"_a);
        mod.def("constant", constant<double>,  "datacleaningobject"_a, "array"_a, doccst);

        char * docclip = "Removes aberrant values.\n\n"
                "A value at position *n* is aberrant if either or both:\n\n"
                "* |z[n] - median(z)| > maxabsvalue\n"
                "* |(z[n+1]-z[n-1])/2-z[n]| > maxderivate\n\n"
                "Aberrant values are replaced by\n\n"
                "* *NaN* if *clip* is true,\n"
                "* *maxabsvalue ± median*, whichever is closest, if *clip* is false.\n\n"
                "returns: *True* if the number of remaining values is too low";
        mod.def("clip", clip<float>,
                "datacleaningobject"_a, "clip"_a, "zero"_a, "array"_a);
        mod.def("clip", clip<double>,
                "datacleaningobject"_a, "clip"_a, "zero"_a, "array"_a, docclip);

    }
}
