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

// matrix scoreparams(ndarray params, ndarray data){
//   // translate from python to C++
//   // apply scoreparam for each element in cparams,cdata
//   blas::matrix<double> score(infopar.shape[0],infodat.shape[0],0);
//   for (ssize_t r=0;r<infopar.shape[0];++r){
//     for (ssize_t col=0;col<infodat.shape[0];++col){
//       score(r,col) = scoreparam(blas::row(cparams,r),row(cdata,col));
//     }
//   }
//   return score;
// }

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

struct OutputEm{
  // all info necessary from 1 EM step
  matrix score;
  matrix rates;
  matrix params;
};


struct OutputMaximization{
  matrix rates;
  matrix params;
};




blas::vector maximizeparam(blas::vector pz_x,matrix data){
  // maximizes a single parameter
  return;
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

OutputMaximization maximization( const matrix &data, matrix pz_x){
  // returns nex iteration of rates, params

  // compute nrates from pz_x
  
  // normalize according to data in npz_x
  auto norm = blas::column(pz_x,0);
  // std::accumulate 
  for (unsigned c=1; c<pz_x.size2();++c)
    norm+=blas::column(pz_x,c);
  matrix npz_x(pz_x);

  for (unsigned r=0;r<npz_x.size1();++r){
    for (unsigned c=0;c<npz_x.size2();++c){
      npz_x(r,c)/=norm(r);
    }
  }
  
  // maximize each params
  for (unsigned r=0;r<npz_x.size1();++r){
    
  }
  OutputMaximization output;
  return output;
}

OutputEm emstep(const matrix &data, matrix &rates, matrix &params){
  //Expectation then Maximization steps of EM
  auto score = scoreparams(data,params);
  auto pz_x  = blas::prod(score,rates);
  auto norm = blas::row(pz_x,0);
  for (unsigned r=1; r<pz_x.size1();++r)
    norm+=blas::row(pz_x,r);

  // renormalize probability per peak
  // yes, could do better
  for (unsigned r=0u, nrows=pz_x.size1(); r<nrows;++r){ 
    for (unsigned c=0u, ncols=pz_x.size2();c<ncols;++c){
      pz_x(r,c)/=norm(c);
    }
  }

  maximized = maximization(data,pz_x);
  rates	    = maximized.rates;
  params    = maximized.params;

  // note : score corresponds to previous set of params
  OneRun output;
  output.score=score;
  output.rates=rates;
  output.params=params;
  return output;
}

void emrunnner(ndarray data, ndarray params,ssize_t nsteps){
  // convert to matrices, run n times, return
  auto infopar = params.request();
  auto infodat = data.request();
  auto cparams = arraytomatrix(params);
  auto cdata   = arraytomatrix(data);
  OutputEm emcall;
  for (ssize_t it=0;it<nsteps;++it){
    emcall = emstep(data,rates,params);
  }
  // reconvert to numpy array
  
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
