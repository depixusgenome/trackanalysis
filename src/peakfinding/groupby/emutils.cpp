#include"emutils.h"
/*
  collection of functions too costly for python
  implementing the EM step in c++ for speed up
  could be further optimized...
  investigate use of ndarray from start to finish
*/
namespace peakfinding{
namespace emutils{
    
    double normpdf(double loc,double var,double pos){
	return exp(-0.5*(pow(pos-loc,2)/var))/(sqrt(2*PI*var));
    }
    
    double exppdf(double loc,double scale,double pos){
	return loc>pos?0:exp((loc-pos)/scale)/scale;
    }
    
    double pdfparam(blas::vector<double> param,blas::vector<double> datum){
	double pdf = 1.;
	for (uint it=0;
	     it<param.size()-2;
	     it+=2)
	    {
		pdf *= normpdf(param(it),param(it+1),datum[0]); // datum[0] to change
	    }
	return pdf*exppdf(param[param.size()-2],param[param.size()-1],datum[datum.size()-1]);
    }
    
    double scoreparam(blas::vector<double> param, blas::vector<double> datum){
	if (pow(datum(0)-param(0),2)>2*param(1))
	    return PRECISION;
	return pdfparam(param,datum);
    }
    
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
    
    matrix scoreparams(const matrix &data,const matrix &params){
	// apply scoreparam for each element in cparams,cdata
	matrix score(params.size1(),data.size1(),0);
	for (unsigned r=0,nrows=params.size1();r<nrows;++r){
	    for (unsigned col=0,ncols=params.size1();col<ncols;++col){
		score(r,col) = scoreparam(blas::row(params,r),row(data,col));
	    }
	}
	return score;
    }
    
    
    matrix maximizeparam(const matrix &data,matrix pz_x){
	// or (const matrix &data , matrix pz_x)
	// maximizes (all) parameters to reduce data manipulations 
	// proba is a row of npz_x
	const unsigned DCOLS = data.size2();
	const unsigned DROWS = data.size1();
	auto	spdata	 = blas::subrange(data,0,DROWS,0,DCOLS-1);
	auto	spdata_t = blas::trans(spdata);
	
	// new spatial means are rows of wspdata; // ok
	auto wspdata = blas::prod(pz_x,spdata); // new mean values
	// new mean of time is zero; // ok
	// general covariance, currently restricting to diagonal terms
	
	//auto cov = blas::prod(spdata_t,wspdata);// wrong ncov, must be estimated row of pz_x per row
	
	// spatial cov is the diagonal of cov
	
	auto tdata  = blas::column(data,DCOLS-1);
	const unsigned NPCOLS = 2*DCOLS-1;
	matrix newparams(pz_x.size1(),NPCOLS+1,0);
	matrix ncov(DCOLS-1,DCOLS-1);
	//blas::vector<double> tmpwdata(DROWS);
	matrix tmpwdata(DCOLS,DCOLS-1,0);
	matrix diagproba(DCOLS,DCOLS,0);
	// the new duration scale is the sum of the element product of row * data[:,-1]
	blas::vector<double> row, prod;
	blas::vector<double> ones(DROWS,1.);
	for (unsigned it=0u,nrows=pz_x.size1();it<nrows;++it){
	    row = blas::row(pz_x,it);
	    for (unsigned dite=0;dite<DCOLS;++dite)
		diagproba(dite,dite)=row(dite);
	    
	    prod = blas::element_prod(row,tdata);
	    newparams(it,NPCOLS) = blas::inner_prod(prod,ones); // duration scale 
	    // computing new covariance matrix
	    tmpwdata = blas::prod(diagproba,spdata);
	    ncov     = blas::prod(spdata_t,tmpwdata);
	    // need to add the spatial means and covariance a row at a time
	    for (unsigned dim=0,maxdim=DCOLS;dim<maxdim;++dim){
		newparams(it,2*dim)   = wspdata(it,dim);	// mean
		// restricting cov to single value
		newparams(it,2*dim+1) = ncov(dim,dim)>PRECISION?ncov(dim,dim):PRECISION;	// cov
	    }
	}
	
	// space mean, space cov, duration mean, duration cov
	return newparams;
    }
    
    MaximizedOutput maximization(const matrix &data, matrix pz_x){
	// returns next iteration of rates, params
	
	// normalize according to data in npz_x
	auto norm = blas::column(pz_x,0);
	for (unsigned c=1; c<pz_x.size2();++c)
	    norm+=blas::column(pz_x,c);
	matrix npz_x(pz_x);
	
	matrix nrates(pz_x.size1(),1);
	for (unsigned r=0, nrows=pz_x.size1();r<nrows;++r){
	    for (unsigned c=0, ncols=pz_x.size2();c<ncols;++c){
		npz_x(r,c)/=norm(r);
	    }
	    nrates(r,1)=norm(r);
	}
	nrates/=pz_x.size2();
	
	MaximizedOutput output;
	output.rates  = nrates;
	output.params = maximizeparam(data,npz_x);
	return output;
    }
    
    void emstep(const matrix &data, matrix &rates, matrix &params){
	//Expectation then Maximization steps of EM
	auto score = scoreparams(data,params);
	auto ones  = matrix(1,score.size2(),1.); // check this
	auto bigrates = blas::prod(rates,ones); // duplicating rates 
	matrix pz_x = blas::element_prod(score,bigrates);
	auto norm = blas::row(pz_x,0);
	for (unsigned r=1; r<pz_x.size1();++r)
	    norm+=blas::row(pz_x,r);
	
	// renormalize probability per peak
	for (unsigned r=0u, nrows=pz_x.size1(); r<nrows;++r){ 
	    for (unsigned c=0u, ncols=pz_x.size2();c<ncols;++c){
		pz_x(r,c)/=norm(c);
	    }
	}
	
	MaximizedOutput maximized = maximization(data,pz_x);
	rates	    = maximized.rates;
	params    = maximized.params;
	
	return;
    }
    
    OutputPy emrunner(ndarray pydata, ndarray pyrates, ndarray pyparams,unsigned nsteps){
	// convert to matrices, run n times, return
	auto	infopar = pyparams.request();
	auto	infodat = pydata.request();
	auto	params	= arraytomatrix(pyparams);
	auto	rates	= arraytomatrix(pyrates);
	auto	data	= arraytomatrix(pydata);
	for (ssize_t it=0;it<nsteps;++it){
	    emstep(data,rates,params);
	}
		// updated score to match with rates & params
	auto	score = scoreparams(data,params);
	// back to numpy array
	ndarray	outparams({params.size1(),params.size2()},
			  {params.size2()*sizeof(double),sizeof(double)},
			  &(params.data()[0]));
	ndarray	outrates({rates.size1(),rates.size2()},
						 {rates.size2()*sizeof(double),sizeof(double)},
			 &(rates.data()[0]));
	ndarray	outscore({score.size1(),score.size2()},
			 {score.size2()*sizeof(double),sizeof(double)},
			 &(score.data()[0]));
	
	OutputPy	output;
	output.score  = outscore;
	output.rates  = outrates;
	output.params = outparams;
	return output;
    }
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
