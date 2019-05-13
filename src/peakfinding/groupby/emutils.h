#pragma once
#ifndef EMUTILS_H
#define EMUTILS_H
#include<iostream>
#include<float.h>
#include<math.h>
#ifdef __GNUC__
# define MAC_OS_X_VERSION_MIN_REQUIRED 0
# ifndef __cpp_noexcept_function_type
#   define __cpp_noexcept_function_type 0
# endif
# ifndef __NVCC___WORKAROUND_GUARD
#   define __NVCC___WORKAROUND_GUARD 0
#   define __NVCC__ 0
# endif
# ifndef __clang__
#   define __clang_major__ 0
#   define __clang_major___WORKAROUND_GUARD 0
#   if (__GNUC__ == 7 || (__GNUC__ == 8 && __GNUC_MINOR__ <= 3))
#     pragma GCC diagnostic push
#     pragma GCC diagnostic ignored "-Wdeprecated-declarations"
#     pragma GCC diagnostic ignored "-Wsuggest-attribute=noreturn"
#     pragma GCC diagnostic ignored "-Wmisleading-indentation"
#     pragma GCC diagnostic ignored "-Wparentheses"
#   endif
# else
#   if (__clang_major__ <= 8)
#     pragma GCC diagnostic push
#     pragma GCC diagnostic ignored "-Wmissing-noreturn"
#     pragma GCC diagnostic ignored "-Wunused-parameter"
#   endif
# endif
#endif
#include<boost/numeric/ublas/matrix.hpp>
#include<boost/numeric/ublas/matrix_proxy.hpp>
#include<boost/numeric/ublas/vector_proxy.hpp>
#include<boost/numeric/ublas/io.hpp>
#ifdef __GNUC__
# ifndef __clang__
#   if (__GNUC__ == 7 || (__GNUC__ == 8 && __GNUC_MINOR__ <= 3))
#     pragma GCC diagnostic pop
#   endif
# else
#   if (__clang_major__ <= 8)
#     pragma GCC diagnostic pop
#   endif
# endif
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
