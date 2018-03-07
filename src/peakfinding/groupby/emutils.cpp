#include"emutils.h"


/*
  collection of functions too costly for python
  implementing the EM step in c++ for speed up
  needs to replace expression with diagproba
*/

namespace peakfinding{
    namespace emutils{
	double PRECISION = 1e-9;
	double PI=3.14159;
	
	double normpdf(double loc,double var,double pos){
	    return exp(-0.5*(pow(pos-loc,2)/var))/(sqrt(2*PI*var));
	}
	
	double exppdf(double loc,double scale,double pos){
	    return loc>pos?0:exp((loc-pos)/scale)/scale;
	}
	
	double pdfparam(blas::vector<double> param,blas::vector<double> datum){
	    double pdf = 1.;
	    for (uint it=0;it<param.size()-2;it+=2){
		pdf *= normpdf(param(it),param(it+1),datum[it/2]); // datum[0] to change
	    }
	    return pdf*exppdf(param[param.size()-2],param[param.size()-1],datum[datum.size()-1]);
	}
	
	double scoreparam(blas::vector<double> param, blas::vector<double> datum){
	    return pdfparam(param,datum);
	}
	
	matrix scoreparams(const matrix &data,const matrix &params){
	    // apply scoreparam for each element in cparams,cdata
	    matrix score(params.size1(),data.size1(),0);
	    for (unsigned r=0,nrows=params.size1();r<nrows;++r){
		for (unsigned col=0,ncols=data.size1();col<ncols;++col){
		    score(r,col) = scoreparam(blas::row(params,r),row(data,col));
		}
	    }
	    matrix tmp(params.size1(),data.size1(),10*PRECISION);
	    score+=tmp;
	    return score;
	}
	
	// this function can be improved
	// must change creation of diagproba to row * matrix
	matrix maximizeparam(const matrix &data,matrix pz_x,double uppercov,double lowercov){
	    // maximizes (all) parameters to reduce data manipulations 
	    // proba is a row of npz_x
	    const unsigned DCOLS = data.size2();
	    const unsigned DROWS = data.size1();
	    auto spdata 	 = blas::subrange(data,0,DROWS,0,DCOLS-1);
	    auto spdata_t        = blas::trans(spdata);

	    // new spatial means are rows of wspdata;
	    auto wspdata = blas::prod(pz_x,spdata); // new mean values
	    // new mean of time is zero;
	    
	    auto tdata  = blas::column(data,DCOLS-1);
	    const unsigned NPCOLS = 2*DCOLS-1;
	    matrix newparams(pz_x.size1(),NPCOLS+1,0);
	    matrix ncov(DCOLS-1,DCOLS-1);
	    matrix tmpwdata(DCOLS,DCOLS-1,0);
	    matrix diagproba(DROWS,DROWS,0);
	    // the new duration scale is the sum of the element product of row * data[:,-1]
	    blas::vector<double> row, prod;
	    blas::vector<double> ones(DROWS,1.);
	    matrix tmpcenter(DROWS,DCOLS-1); // center wspdata on parameter mean
	    matrix ONEROWS(DROWS,1,1.);
	    matrix centered(spdata.size1(),spdata.size2(),0.);
	    matrix centered_t(spdata.size2(),spdata.size1(),0.); // transposed
	    matrix wcentered(spdata.size1(),spdata.size2(),0.); // weighted
	    for (unsigned it=0u,nrows=pz_x.size1();it<nrows;++it){
		row = blas::row(pz_x,it);
		for (unsigned dite=0;dite<DROWS;++dite)
		    diagproba(dite,dite)=row(dite);
		
		prod = blas::element_prod(row,tdata);
		newparams(it,NPCOLS) = blas::inner_prod(prod,ones); // duration scale 
		// computing new covariance matrix
		// centering data
		tmpcenter  = blas::prod(ONEROWS,blas::subrange(wspdata,it,it+1,0,DCOLS-1));
		centered   = spdata-tmpcenter;
		centered_t = blas::trans(centered);
		wcentered  = blas::prod(diagproba,centered);
		ncov	   = blas::prod(centered_t,wcentered);
		// need to add the spatial means and covariance a row at a time
		for (unsigned dim=0,maxdim=DCOLS-1;dim<maxdim;++dim){
		    newparams(it,2*dim)   = wspdata(it,dim);	// mean
		    if (ncov(dim,dim)>uppercov){
			newparams(it,2*dim+1)=uppercov;
		    }
		    else if(ncov(dim,dim)<lowercov){
			newparams(it,2*dim+1)=lowercov;
		    }
		    else{
			newparams(it,2*dim+1)=ncov(dim,dim);
		    }
		}
		
	    }

	    // after testing it is advised to leave some flexibility for peaks
	    return newparams;
	}
	
	MaximizedOutput maximization(const matrix &data,
				     matrix pz_x,
				     double uppercov,
				     double lowercov){
	    // returns next iteration of rates, params
	    // normalize according to data in npz_x
	    blas::vector<double> norm(pz_x.size1(),0.);
	    for (unsigned c=0; c<pz_x.size2();++c)
	    	norm+=blas::column(pz_x,c);
	    matrix npz_x(pz_x);
	    
	    matrix nrates(pz_x.size1(),1,1.);
	    for (unsigned r=0u, nrows=pz_x.size1();r<nrows;++r){
	    	for (unsigned c=0u, ncols=pz_x.size2();c<ncols;++c){
	    	    npz_x(r,c)/=norm(r);
	    	}
	    	nrates(r,0)=norm(r);
	    }
	    nrates/=pz_x.size2();
	    MaximizedOutput output;
	    output.rates  = nrates;
	    output.params = maximizeparam(data,npz_x,uppercov,lowercov);
	    return output;
	}

	matrix getpz_x(const matrix& score,const  matrix& rates){
	    auto ones = matrix(1,score.size2(),1.);
	    auto bigrates  = blas::prod(rates,ones);
	    matrix pz_x = blas::element_prod(score,bigrates);
	    blas::vector<double> norm(pz_x.size2(),0.);
	    for (unsigned r=0u, nrows=pz_x.size1();r<nrows;++r)
	    	norm+=blas::row(pz_x,r);

	    // renormalize probability per peak
	    for (unsigned r=0u, nrows=pz_x.size1(); r<nrows;++r){ 
	    	for (unsigned c=0u, ncols=pz_x.size2();c<ncols;++c){
	    	    pz_x(r,c)/=norm(c);
	    	}
	    }
	    
	    return pz_x;
	}
	
	void emstep(matrix &data, matrix &rates, matrix &params,
		    double uppercov,
		    double lowercov){
	    // Expectation then Maximization steps of EM
	    auto score = scoreparams(data,params);
	    /*
	    auto ones  = matrix(1,score.size2(),1.);
	    auto bigrates = blas::prod(rates,ones);// can be optimized
	    matrix pz_x = blas::element_prod(score,bigrates);
	    blas::vector<double> norm(pz_x.size2(),0.);
	    for (unsigned r=0u, nrows=pz_x.size1();r<nrows;++r)
	    	norm+=blas::row(pz_x,r);

	    // renormalize probability per peak
	    for (unsigned r=0u, nrows=pz_x.size1(); r<nrows;++r){ 
	    	for (unsigned c=0u, ncols=pz_x.size2();c<ncols;++c){
	    	    pz_x(r,c)/=norm(c);
	    	}
	    }
	    */
	    matrix pz_x = getpz_x(score,rates);	    
	    MaximizedOutput maximized = maximization(data,pz_x,uppercov,lowercov);
	    rates  = maximized.rates;
	    params = maximized.params;
	    return;
	}
	
    }
}
