#pragma once
#ifndef EMUTILS_H
#define EMUTILS_H
#include<iostream>
#include<float.h>
#include<math.h>
#include "peakfinding/groupby/emutils_boost.h"

namespace peakfinding{
    namespace emutils{
	namespace blas=boost::numeric::ublas;
	using  matrix = blas::matrix<double>;
	double llikelihood(const matrix& ,const matrix&);
	struct MaximizedOutput{matrix rates,params;};
	double normpdf(double loc,double var,double pos);
	double exppdf(double loc,double scale,double pos);
	double pdfparam(blas::vector<double> ,blas::vector<double>);
	double logpdfparam(blas::vector<double> ,blas::vector<double>);
	void   oneemstep(matrix&, matrix&, matrix&,double);
	void   emsteps(matrix&, matrix&, matrix&,size_t,double,double);
	double scoreparam(blas::vector<double> ,blas::vector<double>);
	matrix scoreparams(const matrix &, const matrix &);
	matrix logscoreparams(const matrix &, const matrix &);
	matrix getpz_x(const matrix &, const matrix &);
	matrix maximizeparam(const matrix &, matrix,double,double);
	MaximizedOutput maximization(const matrix &, matrix,double,double);
    }
}
#endif
