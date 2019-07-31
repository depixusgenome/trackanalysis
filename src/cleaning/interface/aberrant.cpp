#include "cleaning/interface/aberrant.h"
#include "cleaning/interface/rules_doc.h"
#include "cleaning/interface/datacleaning.h"

namespace cleaning::datacleaning::aberrant { namespace { // fromkwa specializations
    using namespace cleaning::datacleaning;
    template <typename T>
    void _constant(py::object self, ndarray<T> pydata)
    {
        if(py::hasattr(self, "constants"))
            self = self.attr("constants");

        auto a = self.attr("mindeltarange").cast<size_t>();
        auto b = self.attr("mindeltavalue").cast<T>();
        ConstantValuesSuppressor<T> itm; itm.mindeltavalue = b; itm.mindeltarange = a;
        itm.apply(pydata.size(), pydata.mutable_data());
    }

    template <typename T>
    void _clip(py::object self, bool doclip, float azero, ndarray<T> pydata)
    {
        if(py::hasattr(self, "derivative"))
            self = self.attr("constants");
        auto a = self.attr("maxabsvalue").cast<T>();
        auto b = self.attr("maxderivate").cast<T>();
        DerivateSuppressor<T> itm; itm.maxabsvalue = a; itm.maxderivate = b;
        itm.apply(pydata.size(), pydata.mutable_data(), doclip, azero);
    }
}}

namespace cleaning::datacleaning::aberrant { namespace { // fromkwa specializations
    using namespace py::literals;
    using namespace cleaning::datacleaning;

    void constants(py::module & mod)
    {
        using CLS = ConstantValuesSuppressor<float>;
        auto  doc = CONSTANT_DOC;
        mod.def("constant", _constant<float>,  "datacleaningobject"_a, "array"_a);
        mod.def("constant", _constant<double>,  "datacleaningobject"_a, "array"_a, doc);

        py::class_<CLS> cls(mod, "ConstantValuesSuppressor", doc);
        cls.def_readwrite("mindeltarange", &CLS::mindeltarange)
           .def_readwrite("mindeltavalue", &CLS::mindeltavalue)
           .def_static(
                   "zscaledattributes", 
                    []() { return py::make_tuple("mindeltavalue"); }
           )
           .def(
                   "rescale", 
                    [](CLS const & self, float val)
                    {
                        auto cpy           = self;
                        cpy.mindeltavalue *= val;
                        return cpy;
                    }
           )
           .def("apply",
                [](CLS const & self, ndarray<float> arr)
                { self.apply(arr.size(), arr.mutable_data()); });
        _defaults(cls);
    }

    void derivative(py::module & mod)
    {
        auto doc =  DERIVATIVE_DOC;

        mod.def("clip", _clip<float>,
                "datacleaningobject"_a, "clip"_a, "zero"_a, "array"_a);
        mod.def("clip", _clip<double>,
                "datacleaningobject"_a, "clip"_a, "zero"_a, "array"_a, doc);

        using CLS = DerivateSuppressor<float>;
        py::class_<CLS> cls(mod, "DerivateSuppressor", doc);
        cls.def_readwrite("maxderivate", &CLS::maxderivate)
           .def_readwrite("maxabsvalue", &CLS::maxabsvalue)
           .def_static(
                   "zscaledattributes", 
                    []() { return py::make_tuple("maxabsvalue", "maxderivate"); }
           )
           .def(
                   "rescale", 
                    [](CLS const & self, float val)
                    {
                        auto cpy = self;
                        cpy.maxabsvalue *= val;
                        cpy.maxderivate *= val;
                        return cpy;
                    }
           )
           .def("apply",
                [](CLS const & self, ndarray<float> arr, bool clip, float zero)
                { self.apply(arr.size(), arr.mutable_data(), clip, zero); });
        _defaults(cls);
    }

    void localnans(py::module & mod)
    {
        using CLS = LocalNaNPopulation;
        auto doc = R"_(Removes frames which have NaN values to their right and their left)_";
        py::class_<CLS> cls(mod, "LocalNaNPopulation", doc);
        cls.def_readwrite("window", &CLS::window)
           .def_readwrite("ratio",  &CLS::ratio)
           .def("apply",
                [](CLS const & self, ndarray<float> arr)
                { self.apply(arr.size(), arr.mutable_data()); });
        _defaults(cls);
    }

    void nanislands(py::module & mod)
    {
        auto doc = NANISLANDS_DOC;

        using CLS = NaNDerivateIslands;
        py::class_<CLS> cls(mod, "NaNDerivateIslands", doc);
        cls.def_readwrite("riverwidth",  &CLS::riverwidth)
           .def_readwrite("islandwidth", &CLS::islandwidth)
           .def_readwrite("ratio",       &CLS::ratio)
           .def_readwrite("maxderivate", &CLS::maxderivate)
           .def_static(
                   "zscaledattributes", 
                    []() { return py::make_tuple("maxderivate"); }
           )
           .def(
                   "rescale", 
                    [](CLS const & self, float val)
                    {
                        auto cpy         = self;
                        cpy.maxderivate *= val;
                        return cpy;
                    }
           )
           .def("apply", [](CLS const & self, ndarray<float> arr)
                { self.apply(arr.size(), arr.mutable_data()); });
        _defaults(cls);
    }

    void abb(py::module & mod)
    {
        auto doc = ABB_DOC;
        using CLS = AberrantValuesRule;
        py::class_<CLS> cls(mod, "AberrantValuesRule", doc);
        cls.def_readwrite("constants",  &CLS::constants)
           .def_readwrite("derivative", &CLS::derivative)
           .def_readwrite("localnans",  &CLS::localnans)
           .def_readwrite("islands",    &CLS::islands)
           .def_static(
                   "zscaledattributes", 
                    []() {
                        return py::make_tuple(
                            "mindeltavalue", "maxabsvalue", "maxderivate", "cstmaxderivate"
                        ); 
                    }
           )
           .def(
                   "rescale", 
                    [](CLS const & self, float val)
                    {
                        auto cpy = self;
                        cpy.constants.mindeltavalue *= val;
                        cpy.derivative.maxabsvalue  *= val;
                        cpy.derivative.maxderivate  *= val;
                        cpy.islands.maxderivate     *= val;
                        return cpy;
                    }
           )
           .def("aberrant",
                [](CLS const & self, ndarray<float> arr, bool clip, float ratio)
                { 
                    float * data = arr.mutable_data();
                    size_t  sz   = arr.size();
                    size_t  cnt  = sz;
                    {
                        py::gil_scoped_release _;
                        self.apply(sz, data, clip);
                        for(size_t i = 0u; i < sz; ++i)
                            if(!std::isfinite(data[i]))
                                --cnt;
                    }
                    return cnt < size_t(sz*ratio);
                },
                py::arg("beaddata"), py::arg("clip") = false, py::arg("ratio") = .8
            );
        _defaults(cls);
    }
}}

namespace cleaning::datacleaning::aberrant {
    void pymodule(py::module & mod)
    {
        constants(mod);
        derivative(mod);
        localnans(mod);
        nanislands(mod);
        abb(mod);
    }
}
