#pragma once
#ifndef EMUTILS_H
#define EMUTILS_H
#include<iostream>
#include<math.h>
#include<boost/numeric/ublas/matrix.hpp>
#include<boost/numeric/ublas/matrix_proxy.hpp>
#include<boost/numeric/ublas/vector_proxy.hpp>
#include<boost/numeric/ublas/io.hpp>


namespace peakfinding{
namespace emutils{
namespace blas=boost::numeric::ublas;
using  matrix = blas::matrix<double>;
struct MaximizedOutput{matrix rates,params,score;};
double normpdf(double loc,double var,double pos);
double exppdf(double loc,double scale,double pos);
double pdfparam(blas::vector<double> ,blas::vector<double>);
void   emstep(matrix&, matrix&, matrix&);
double scoreparam(blas::vector<double> ,blas::vector<double>);
matrix scoreparams(const matrix &, const matrix &);
matrix maximizeparam(const matrix&, matrix);
MaximizedOutput maximization(const matrix&, matrix);
}}
#endif
