#ifndef EMUTILS_H
#define EMUTILS_H
#include<iostream>
#include<math.h>
#include<pybind11/pybind11.h>
#include<pybind11/numpy.h>
#include<pybind11/stl.h>
#include<boost/numeric/ublas/matrix.hpp>
#include<boost/numeric/ublas/matrix_proxy.hpp>
#include<boost/numeric/ublas/vector_proxy.hpp>

#include<boost/numeric/ublas/io.hpp>
namespace py=pybind11;
namespace blas=boost::numeric::ublas;

using ndarray = py::array_t<double, py::array::c_style>;
using  matrix = blas::matrix<double>;

double PRECISION = 1e-10;
double PI=3.14159;

struct OutputPy{ndarray score,rates,params;};
struct MaximizedOutput{matrix rates,params,score;};

double normpdf(double loc,double var,double pos);
double exppdf(double loc,double scale,double pos);
double pdfparam(blas::vector<double> ,blas::vector<double>);
void   emstep(matrix&, matrix&, matrix&);
matrix arraytomatrix(ndarray);
double scoreparam(blas::vector<double> ,blas::vector<double>);
matrix scoreparams(const matrix &, const matrix &);
matrix maximizeparam(const matrix&, matrix);
MaximizedOutput maximization(const matrix&, matrix);

OutputPy emrunner(ndarray,ndarray,ndarray,unsigned);



#endif
