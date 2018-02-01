#include"emutils.h"
/*
  collection of functions too costly for python
  implementing the EM step in c++ for speed up
  need to decide implementation of parameters
  investigate use of ndarray from start to finish
*/

using namespace std;
double normpdf(double loc,double var,double pos){
  return exp(-0.5*(pow(pos-loc,2)/var))/(sqrt(2*PI*var));
}

double exppdf(double loc,double scale,double pos){
  return loc>pos?0:exp((loc-pos)/scale)/scale;
}

double pdfparam(vector<double> param,vector<double> datum){
  double pdf = 1.;
  for (vector<double>::iterator it=param.begin();
       it!=param.end()-2;
       it+=2)
    {
      pdf *= normpdf(*it,*(it+1),datum[0]); // datum[0] to change
    }
  return pdf*exppdf(param[param.size()-2],param[param.size()-1],datum[datum.size()-1]);
}

double scoreparam(vector<double> param, vector<double> datum){
  if (pow(datum[0]-param[0],2)>2*param[1])
    return PRECISION;
  return pdfparam(param,datum);
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

vector<double> array1dtovector(ndarray arr){
  py::buffer_info info=arr.request();
  if (info.ndim!=1)
    throw runtime_error("incorrect dimension of array. Should be 1");
  
  vector<double> varr(info.shape[0],0.);
  for (unsigned i=0;i<varr.size();++i)
    {
      cout<<"adding "<<((double*)info.ptr)[i]<<endl;
      varr[i]=((double*)info.ptr)[i];
    }
  return varr;
}

vector<vector<double> > arraytovector(ndarray arr){
  //check type
  auto vals = arr.unchecked<2>();
  vector<vector<double> > ret (vals.shape(0), vector<double>(vals.shape(1),0));
  
  for (ssize_t row=0;row<vals.shape(0);row++){
    for (ssize_t col=0;col<vals.shape(1);col++){
      ret[row][col]=*vals.data(row,col);
    }
  }
  return ret;
}


blas::matrix<double> arraytomatrix(ndarray arr){
  auto vals = arr.unchecked<2>();
  blas::matrix<double>ret(vals.shape(0),vals.shape(1));
  for (ssize_t row=0;row<vals.shape(0);row++){
    for (ssize_t col=0;col<vals.shape(1);col++){
      ret(row,col)=*vals.data(row,col);
    }
  }
  return ret;
}

ndarray scoreparams(ndarray params, ndarray data){
  // translate from python to C++
  py::buffer_info infopar = params.request();
  py::buffer_info infodat = data.request();

  // vector<vector<double> > score (infopar.shape[0],vector<double>(infodat.shape[0],0));
  // vector<vector<double> > cparams = arraytovector(params);
  // vector<vector<double> > cdata   = arraytovector(data);
  // apply scoreparam for each element in cparams,cdata
  blas::matrix<double> score(infopar.shape[0],infodat.shape[0],0);
  blas::matrix<double> cparams = arraytomatrix(params);
  blas::matrix<double> cdata   = arraytomatrix(data);
  for (ssize_t r=0;r<infopar.shape[0];++r){
    for (ssize_t col=0;col<infodat.shape[0];++col){
      score(r,col) = scoreparam(blas::row(cparams,r),row(cdata,col));
    }
  }
  return params;
}
PYBIND11_MODULE(emutils,mod){
  mod.doc()="c++ version of EM";
  mod.def("normpdf",&normpdf,"computes the pdf of a normal distribution");
  mod.def("exppdf",&exppdf,"computes the pdf of a exponential distribution");
  mod.def("scoreparams",&scoreparams,"compute the pdf of a params (spatial+duration)");
}
