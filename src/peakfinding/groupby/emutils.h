#ifndef EMUTILS_H
#define EMUTILS_H
#include<iostream>
#include<math.h>
#include<pybind11/pybind11.h>
#include<pybind11/numpy.h>
#include<boost/numeric/ublas/matrix.hpp>
#include<boost/numeric/ublas/matrix_proxy.hpp>
#include<boost/numeric/ublas/vector_proxy.hpp>

#include<boost/numeric/ublas/io.hpp>
double PRECISION = 1e-10;
double PI=3.14159;
double normpdf(double loc,double var,double pos);
double exppdf(double loc,double scale,double pos);

namespace py=pybind11;
namespace blas=boost::numeric::ublas;
using ndarray = py::array_t<double, py::array::c_style>;

typedef blas::matrix<double> matrix;
#endif
