#include "utils/pybind11.hpp"
#include "cleaning/interface/interface.h"

DPX_INTERFACE(cleaning::beadsubtraction)
DPX_INTERFACE(cleaning::datacleaning::aberrant)
DPX_INTERFACE(cleaning::datacleaning::rules)
namespace cleaning { //module
    void pymodule(py::module & mod)
    {
        DPX_INTERFACE_CALL(cleaning::beadsubtraction)
        DPX_INTERFACE_CALL(cleaning::datacleaning::aberrant)
        DPX_INTERFACE_CALL(cleaning::datacleaning::rules)
    }
}
