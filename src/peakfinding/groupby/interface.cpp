#include<pybind11/pybind11.h>
#ifndef PYBIND11_HAS_VARIANT
# define PYBIND11_HAS_VARIANT 0      // remove compile-time warnings
# define PYBIND11_HAS_EXP_OPTIONAL 0
# define PYBIND11_HAS_OPTIONAL 0
#endif
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

	struct 
#if __GNUC__ == 7 && __GNUC_MINOR__ == 3
    __attribute__ ((visibility("hidden")))
#endif
    OutputPy
    {
        ndarray score,rates,params;
    };

	OutputPy emrunner(ndarray pydata,
			  ndarray pyrates,
			  ndarray pyparams,
			  size_t nsteps,
			  double lowercov,
			  double tol){
	    // convert to matrices, run n times, return
	    auto    infopar	= pyparams.request();
	    auto    infodat	= pydata.request();
	    matrix    params	= arraytomatrix(pyparams);
	    matrix    rates	= arraytomatrix(pyrates);
	    matrix    data	= arraytomatrix(pydata);
	    
	    emsteps(data,rates,params,nsteps,lowercov,tol);
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

	ndarray pylogscore(ndarray pydata,ndarray pyparams){
	    auto    infopar	= pyparams.request();
	    auto    infodat	= pydata.request();
	    matrix    params	= arraytomatrix(pyparams);
	    matrix    data	= arraytomatrix(pydata);
	    auto    score	= logscoreparams(data,params);
	    ndarray outscore({score.size1(),score.size2()},
	    		     {score.size2()*sizeof(double),sizeof(double)},
	    		     &(score.data()[0]));

	    return outscore;
	}

	ndarray pyscore(ndarray pydata,ndarray pyparams){
	    auto    infopar	= pyparams.request();
	    auto    infodat	= pydata.request();
	    matrix    params	= arraytomatrix(pyparams);
	    matrix    data	= arraytomatrix(pydata);
	    auto    score = scoreparams(data,params);
	    ndarray outscore({score.size1(),score.size2()},
	    		     {score.size2()*sizeof(double),sizeof(double)},
	    		     &(score.data()[0]));

	    return outscore;
	}

	ndarray pypz_x(ndarray pyscore,ndarray pyrates){
	    matrix	score	  = arraytomatrix(pyscore);
	    matrix	rates	  = arraytomatrix(pyrates);
	    auto	pz_x	  = getpz_x(score,rates);
	    ndarray outpz_x({pz_x.size1(),pz_x.size2()},
	    		     {pz_x.size2()*sizeof(double),sizeof(double)},
	    		     &(pz_x.data()[0]));

	    return outpz_x;
	}

	void pymodule(py::module &mod){
	    auto doc = R"_(Runs Expectation Maximization N times)_";
	    mod.def("emrunner",[](ndarray data,ndarray rates,ndarray params,size_t nsteps,double lower, double tol)
	     	    {return emrunner(data,rates,params,nsteps,lower,tol);},doc);
	    mod.def("normpdf",[](double loc,double var, double pos){return normpdf(loc,var,pos);},
		    R"_(compute pdf of normal distribution)_");
	    mod.def("exppdf",[](double loc,double scale, double pos){return exppdf(loc,scale,pos);},
		    R"_(compute pdf of exponential distribution)_");
	    mod.def("emscore",[](ndarray data,ndarray params){return pyscore(data,params);},
		    R"_(returns score matrix)_");
	    mod.def("emlogscore",[](ndarray data,ndarray params){return pylogscore(data,params);},
		    R"_(returns log score matrix)_");
	    mod.def("empz_x",[](ndarray score,ndarray rates){return pypz_x(score,rates);},
		    R"_(returns pz_x matrix)_");

	    pybind11::class_<OutputPy>(mod, "OutputPy")
		.def(pybind11::init<>())
		.def_readwrite("score", &OutputPy::score)
		.def_readwrite("rates", &OutputPy::rates)
		.def_readwrite("params", &OutputPy::params);
	}
    }
}
