#include"emutils.h"
/*
  interface between python and c++
*/

namespace peakfinding{
    namespace emutils{
	void pymodule(py::module &mod){
	    auto doc = R"_(Runs Expectation Maximization N times)_";
	    mod.def("emrunner",[](ndarray &data,ndarray &rates,ndarray &params,unsigned &nsteps)
		    {return emrunnner(data,rates,para,nsteps);},doc);
	    mod.def("normpdf",[](double loc,double var, double pos){return normpdf(loc,var,pos);},
		    R"_(compute pdf of normal distribution)_");
	    mod.def("exppdf",[](double loc,double scale, double pos){return exppdf(loc,scale,pos);},
		    R"_(compute pdf of exponential distribution)_");
	}
    }
    
    
    void pymodule(py::module &mod){
	emutils::pymodule(mod);
    }
}


// PYBIND11_MODULE(emutils, mod) {
//     mod.doc() = "utilitaries functions in C++";
//     mod.def("emrunner",[](ndarray &data,ndarray &rates,ndarray &params,unsigned &nsteps)
// 	    {return emutils::emrunner(data,rates,params,nsteps);},"Runs Expectation Maximization N times");
//     mod.def("normpdf",[](double loc,double var, double pos){return emutils::normpdf(loc,var,pos);},
// 	    "compute pdf of normal distribution");
//     mod.def("exppdf",[](double loc,double scale, double pos){return emutils::exppdf(loc,scale,pos);},
// 	    "compute pdf of exponential distribution");
// }
