#include<pybind11/pybind11.h>
#include<pybind11/numpy.h>
#include<pybind11/stl.h>
#include"emutils.h"

/*
  interface between python and c++
*/

namespace peakfinding{
    namespace py=pybind11;
    namespace emutils{
	using ndarray = py::array_t<double, py::array::c_style>;
	matrix arraytomatrix(const ndarray arr){
	    auto vals = arr.unchecked<2>();
	    matrix ret(vals.shape(0),vals.shape(1));
	    for (ssize_t row=0;row<vals.shape(0);row++){
		for (ssize_t col=0;col<vals.shape(1);col++){
		    ret(row,col)=*vals.data(row,col);
		}
	    }
	    return ret;
	}

	struct OutputPy{ndarray score,rates,params;};

	OutputPy emrunner(ndarray pydata, ndarray pyrates, ndarray pyparams,unsigned nsteps){
	    // convert to matrices, run n times, return
	    auto    infopar = pyparams.request();
	    auto    infodat = pydata.request();
	    matrix    params  = arraytomatrix(pyparams);
	    matrix    rates   = arraytomatrix(pyrates);
	    matrix    data    = arraytomatrix(pydata);
	    
	    for (unsigned it=0;it<nsteps;++it)
	    	emstep(data,rates,params);
	    
	    // updated score to match with rates & params
	    auto    score = scoreparams(data,params);
	    // back to numpy array
	    ndarray outparams({params.size1(),params.size2()},
	    		      {params.size2()*sizeof(double),sizeof(double)},
	    		      &(params.data()[0]));
	    ndarray outrates({rates.size1(),rates.size2()},
	    		     {rates.size2()*sizeof(double),sizeof(double)},
	    		     &(rates.data()[0]));
	    ndarray outscore({score.size1(),score.size2()},
	    		     {score.size2()*sizeof(double),sizeof(double)},
	    		     &(score.data()[0]));

	    OutputPy        output;
	    output.score  = outscore;
	    output.rates  = outrates;
	    output.params = outparams;
	    return output;
	}

	void pymodule(py::module &mod){
	    auto doc = R"_(Runs Expectation Maximization N times)_";
	    mod.def("emrunner",[](ndarray data,ndarray rates,ndarray params,unsigned nsteps)
	     	    {return emrunner(data,rates,params,nsteps);},doc);
	    mod.def("normpdf",[](double loc,double var, double pos){return normpdf(loc,var,pos);},
		    R"_(compute pdf of normal distribution)_");
	    mod.def("exppdf",[](double loc,double scale, double pos){return exppdf(loc,scale,pos);},
		    R"_(compute pdf of exponential distribution)_");

	    pybind11::class_<OutputPy>(mod, "OutputPy")
		.def(pybind11::init<>())
		.def_readwrite("score", &OutputPy::score)
		.def_readwrite("rates", &OutputPy::rates)
		.def_readwrite("params", &OutputPy::params);
	}
    }
    
    void pymodule(py::module &mod){
	emutils::pymodule(mod);
    }
}
