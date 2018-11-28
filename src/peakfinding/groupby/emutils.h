#pragma once
#ifndef EMUTILS_H
#define EMUTILS_H
#include<iostream>
#include<float.h>
#include<math.h>
#if __GNUC__ == 7 && __GNUC_MINOR__ == 3
# ifndef __cpp_noexcept_function_type
#   define __cpp_noexcept_function_type 0
# endif
# ifndef __NVCC___WORKAROUND_GUARD
#   define __NVCC___WORKAROUND_GUARD 0
#   define __NVCC__ 0
# endif
# pragma GCC diagnostic ignored "-Wsuggest-attribute=noreturn"
# pragma GCC diagnostic ignored "-Wmisleading-indentation"
#endif
#include<boost/numeric/ublas/matrix.hpp>
#include<boost/numeric/ublas/matrix_proxy.hpp>
#include<boost/numeric/ublas/vector_proxy.hpp>
#include<boost/numeric/ublas/io.hpp>
#if __GNUC__ == 7 && __GNUC_MINOR__ == 3
# pragma GCC diagnostic pop
#endif


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
	void   emsteps(matrix&, matrix&, matrix&,unsigned,double,double);
	double scoreparam(blas::vector<double> ,blas::vector<double>);
	matrix scoreparams(const matrix &, const matrix &);
	matrix logscoreparams(const matrix &, const matrix &);
	matrix getpz_x(const matrix &, const matrix &);
	matrix maximizeparam(const matrix &, matrix,double,double);
	MaximizedOutput maximization(const matrix &, matrix,double,double);
    }
}
#endif
