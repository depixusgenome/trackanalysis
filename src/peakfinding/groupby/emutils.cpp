#include"emutils.h"
/*
  collection of functions too costly for python
  implementing the EM step in c++ for speed up
  could be further optimized...
  investigate use of ndarray from start to finish
*/

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

matrix arraytomatrix(ndarray arr){
  auto vals = arr.unchecked<2>();
  matrix ret(vals.shape(0),vals.shape(1));
  for (ssize_t row=0;row<vals.shape(0);row++){
    for (ssize_t col=0;col<vals.shape(1);col++){
      ret(row,col)=*vals.data(row,col);
    }
  }
  return ret;
}

matrix scoreparams(matrix data, matrix params){
  // apply scoreparam for each element in cparams,cdata
  matrix score(params.size1(),data.size1(),0);
  for (unsigned r=0;r<params.size1();++r){
    for (unsigned col=0;col<params.size1();++col){
      score(r,col) = scoreparam(blas::row(params,r),row(data,col));
    }
  }
  return score;
}



struct OutputMaximization{
  matrix rates;
  matrix params;
};



// def __maximizeparam(self,data,proba):
//           'maximizes a parameter'
//   nmeans = np.array(np.matrix(proba)*data[:,:-1]).ravel()
//   ncov   = np.cov(data[:,:-1].T,aweights = proba ,ddof=0)
//   tscale = np.sum(proba*data[:,-1])
//   return [(nmeans,self.covmap(ncov)),(0.,tscale)]
  
matrix maximizeparam(const matrix &data,matrix pz_x){
  // or (const matrix &data , matrix pz_x)
  // maximizes (all) parameters to reduce data manipulations 
  // proba is a row of npz_x
  const unsigned DCOLS = data.size2();
  const unsigned DROWS = data.size1();
  auto	sdata	 = blas::subrange(data,0,DROWS,0,DCOLS-1);
  auto	spdata_t = blas::trans(spatialdata);

  // new spatial means are rows of wspdata; // ok
  auto wspdata = blas::prod(pz_x,sdata);
  // new mean of time is zero; // ok
  // general covariance, currently restricting to diagonal terms

  //auto cov = blas::prod(spdata_t,wspdata);// wrong ncov, must be estimated row of pz_x per row

  // spatial cov is the diagonal of cov

  auto tdata  = blas::column(data,DCOLS-1);
  const unsigned NPCOLS = 2*DCOLS-1;
  matrix newparams(pz_x.size1(),NPCOLS+1,0);
  // the new duration scale is the sum of the element product of row * data[:,-1]
  blas::vector<double> row, prod;
  blas::vector<double> ones(DROWS,1.);
  for (unsigned it=0u,nrows=pz_x.size1();it<nrows;++it){
    row	 = blas::row(pz_x,it);
    prod = blas::element_prod(row,tdata);
    newparams(it,NPCOLS) = blas::inner_prod(prod,ones);// sum of prod
    // to continue from here
    // ncov must be computed here
    // need to add the spatial means and covariance a row at a time
    for (unsigned dim=0,maxdim=DCOLS;dim<maxdim;++dim){
      newparams(it,2*dim)   = wspdata(it,dim);	//mean
      // restricting cov to single value
      newparams(it,2*dim+1) = cov();	//cov
    }
  }
  // stack correctly the results
  // space mean, space cov, duration mean, duration cov
  return newparams;
}

// def maximization(self,pz_x:np.ndarray,data:np.ndarray):
//         'returns the next set of parameters'
// npz_x = pz_x/np.sum(pz_x,axis=1).reshape(-1,1)

//   nrates   = np.mean(pz_x,axis=1).reshape(-1,1)
//   maximize = partial(self.__maximizeparam,data)
//   params   = np.array(list(map(maximize,npz_x))) # type: ignore
//   if self.covtype is COVTYPE.TIED:
//   meancov       = np.mean(params[:,0,1],axis=0)
// 	params[:,0,1] = meancov
// 	return nrates, params

// should be ok mod some optimizations
OutputMaximization maximization(const matrix &data, matrix pz_x){
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
  
  OutputMaximization output;
  output.rates  = nrates;
  output.params = maximizeparam(data,npz_x);
  return output;
}

// should be ok mod some optimizations
void emstep(const matrix &data, matrix &rates, matrix &params){
  //Expectation then Maximization steps of EM
  auto score = scoreparams(data,params);
  auto ones  = blas::matrix(1,score.size2());
  auto bigrates = blas::prod(rates,ones); // rates duplicated
  auto pz_x = blas::element_prod(score,bigrates); // to check
  auto norm = blas::row(pz_x,0);
  for (unsigned r=1; r<pz_x.size1();++r)
    norm+=blas::row(pz_x,r);

  // renormalize probability per peak
  for (unsigned r=0u, nrows=pz_x.size1(); r<nrows;++r){ 
    for (unsigned c=0u, ncols=pz_x.size2();c<ncols;++c){
      pz_x(r,c)/=norm(c);
    }
  }

  maximized = maximization(data,pz_x);
  rates	    = maximized.rates;
  params    = maximized.params;

  return;
}

// should be ok mod some optimizations
std::list<ndarray> emrunnner(ndarray data, ndarray params,ssize_t nsteps){
  // convert to matrices, run n times, return
  auto infopar = params.request();
  auto infodat = data.request();
  auto cparams = arraytomatrix(params);
  auto cdata   = arraytomatrix(data);
  OutputEm emcall;
  for (ssize_t it=0;it<nsteps;++it){
    emcall = emstep(data,rates,params);
  }
  // back to numpy array
  ndarray pyparams({params.size1(),params.size2()},
		   {params.size2()*sizeof(double),sizeof(double)},
		   &(params.data[0]));
  ndarray pyrates({rates.size1(),rates.size2()},
		   {rates.size2()*sizeof(double),sizeof(double)},
		   &(rates.data[0]));

  // updated score to match with rates & params
  auto score = scoreparams(data,params);
  ndarray pyscore({score.size1(),score.size2()},
		   {score.size2()*sizeof(double),sizeof(double)},
		   &(score.data[0]));

  std::list output;
  output.push_back(pyscore,pyrates,pyparams);
  return output;
}

// correct call to implement within wafbuilder
// needs wrapping of functions into the associated namespace
namespace utils {
  void pymodule(pybind11::module & mod)
  {
    emrunner	:: pymodule(mod);
    normpdf	:: pymodule(mod);
    exppdf	:: pymodule(mod);
  }
}

// PYBIND11_MODULE(emutils,mod){
//   mod.doc()="c++ version of EM";
//   mod.def("normpdf",&normpdf,"computes the pdf of a normal distribution");
//   mod.def("exppdf",&exppdf,"computes the pdf of a exponential distribution");
//   mod.def("scoreparams",&scoreparams,"compute the pdf of a params (spatial+duration)");
// }
