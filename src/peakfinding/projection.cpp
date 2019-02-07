#include <numeric>
#include <cmath>
#include <algorithm>
#include <cassert>
#include "peakfinding/projection.h"
#include "signalfilter/accumulators.hpp"

namespace peakfinding { namespace projection {

namespace {
    long _rnd(DigitizedData   const & data, float ratio)
    { return std::lround((data.precision*ratio)*data.delta); }

    long _rnd(Digitizer       const & data, float ratio)
    { return std::lround((data.precision*ratio)/data.binwidth()); }

    struct _Symm1Iterator
    {
        _Symm1Iterator(long thr, long val)
            : threshold(thr)
        { data[0] = data[1] = val; }

        bool  operator()(long val)
        {
            bool out = std::abs(data[1] - data[0]*.5f - val*.5f) < threshold;
            data[0]  = data[1];
            data[1]  = val;
            return out;
        }

        long                    operator*() const { return data[0]; }
        constexpr static size_t count()           { return 1u; }

        long  threshold;
        private:
            long data[2] = {0, 0};
    };

    struct _DummyIterator
    {
        _DummyIterator(long, long val) : data(val) {}

        bool                    operator()(long)  { return true; }
        long                    operator*() const { return data; }
        constexpr static size_t count()           { return 0u; }
        private:
            long data = 0;
    };

    template<typename T>
    std::vector<size_t> _apply(CycleProjection  const & cnf,
                               DigitizedData    const & data)
    {
        auto i = data.digits.begin(), ie = data.digits.end();

        while(i != ie && *i < 0)
            ++i;

        std::vector<size_t> hist(data.nbins);
        if(i == ie)
            return hist;

        T itr(_rnd(data, cnf.dzratio)*(1<<data.oversampling), *i);

        for(++i; i != ie; ++i)
            if(*i >= 0 && itr(*i))
                ++hist[(*itr)>>data.oversampling];

        for(size_t j = 0u; j < T::count(); ++j)
            if(itr(*itr))
                ++hist[(*itr)>>data.oversampling];

        return hist;
    }

    /* Map a function to a moving sum of along a histogram.
     */
    template <typename T>
    std::vector<float> _toweights(CycleProjection const &  cnf,
                                  DigitizedData   const &  data,
                                  std::vector<size_t>   && hist,
                                  T                        fcn)
    {
        size_t nbins = data.nbins;
        size_t size  = (size_t) _rnd(data, cnf.countratio);

        std::vector<float> weights(nbins);
        if(size == 0)                   /* no summing of multiple indexes */
        {
            for(size_t i = 0u; i < nbins; ++i)
                if(hist[i] >= cnf.countthreshold)
                    weights[i] = fcn(hist[i]);
        } else if(2*size+1 >= nbins)    /* summing *all* indexes */
        {
            float  rng = (cnf.countthreshold*hist.size())/float(2u*size+1u);
            size_t sum = std::accumulate(hist.begin(), hist.end(), size_t(0));
            weights.assign(weights.size(), sum >= rng ? 1.0f : 0.f);
        } else                          /* moving sum of indexes */
        {
            size_t sum = std::accumulate(hist.begin(), hist.begin()+(size-1u), size_t(0));
            size_t i   = 0u;
            size_t ie  = size >= nbins ? 0u : nbins-size-1u;
            float  rng = cnf.countthreshold/float(2u*size+1u);

            /* moving sum: lower edge */
            for(; i < ie && i < size; ++i)
            {
                sum += hist[i+size];
                if(float(sum) >= (i+size)*rng)
                    weights[i] = fcn(sum);
            }

            /* moving sum: middle */
            for(; i < ie; ++i)
            {
                sum += hist[i+size];
                if(float(sum) >= cnf.countthreshold)
                    weights[i] = fcn(sum);
                sum -= hist[i-size];
            }

            /* moving sum: higher edge */
            for(; i < nbins; ++i)
            {
                if(float(sum) >= (nbins-i+size)*rng)
                    weights[i] = fcn(sum);
                sum -= hist[i-size];
            }
        }
        return weights;
    }

    static size_t  const _gaussianratio = 20u;
    static long    const _nexp          = 120l;
    static bool          _init          = false;
    static float         _gaussianvdata[_nexp+1u];

    void _gaussianinit()
    {
        if(!_init)
        {
            for(size_t i = 0u; i < _nexp; ++i)
                const_cast<float*>(_gaussianvdata)[i] = 
                    std::exp(-float(i*i)/(_gaussianratio*_gaussianratio*2));
            _gaussianvdata[_nexp] = 0.0f;
            _init            = true;
        }
    }

    float _gaussian(float val)
    {
        auto iwgt = std::lround(std::abs(val)*_gaussianratio);
        return _gaussianvdata[std::max(0l, std::min(_nexp, iwgt))];
    }

    /* Smooth weights according to their proximity in time (data index) and z (data values).
     * The formula is:
     *
     *                 Sum_{T-δt, T+δt} (weights(t) * gaussian(data(T)-data(t)))
     *  w_new(T) =     _______________________________________________________
     *                  
     *                          Sum_{T-δt, T+δt} (gaussian(data(T)-data(t)))
     */
    std::vector<float> _tsmoothing(CycleProjection const & cnf,
                                   DigitizedData   const & data,
                                   std::vector<float>    & weights)
    {
        _gaussianinit();
        std::vector<float> out  (weights.size());
        long               hsz  ((long) (cnf.tsmoothinglen/2u));
        float              ebin (_rnd(data, cnf.tsmoothingratio)/float(1<<data.oversampling));
        for(long i = 0u, ie  = (long) data.digits.size(); i < ie; ++i)
        {
            if(data.digits[i] < 0l)
                continue;

            float sum = 0.0f;
            float cnt = 0.0f;
            for(long j = -hsz; j <= hsz; ++j)
            {
                auto ind = std::min(std::max(i+j, 0l), ie-1l);
                if(data.digits[ind] < 0l)
                    continue;

                auto wgt  = _gaussian((data.digits[ind]-data.digits[i])*ebin);

                assert(data.digits[ind]>>data.oversampling < weights.size());
                sum      += wgt * weights[data.digits[ind]>>data.oversampling];
                cnt      += wgt;
            }

            assert(data.digits[i]>>data.oversampling < out.size());
            out[data.digits[i]>>data.oversampling] += sum/cnt;
        }
        return out;
    }

    /* Smoothes data according to their in z (data index).
     * The formula is:
     *
     *                 Sum_{T-δt, T+δt} (data(t) * gaussian((T-t)/delta))
     *  d_new(T) =     _______________________________________________________
     *                  
     *                          Sum_{T-δt, T+δt} (gaussian((T-t)/delta))
     */
    void _smoothing(size_t size, long delta, std::vector<float> & data)
    {
        if(delta <= 0l)
            return;

        std::vector<float> expv(size+1);
        float norm = 0.0f;
        for(long i = 0l, ie = long(size); i < ie; ++i)
            norm += (expv[i] = std::exp(-float(i*i)/float(delta*delta*2l)));
        for(long i = 0l, ie = long(size); i < ie; ++i)
            expv[i] /= norm;

        std::vector<float> cpy(data);
        for(long i = 0l, ie = long(data.size()), je = long(size); i < ie; ++i)
        {
            data[i] *= expv[0];
            for(long j = 1l; j <= je; ++j)
                data[i] += (cpy[std::max(0l, i-j)]+cpy[std::min(ie-1l, i+j)])*expv[j];
        }
    }

    std::pair<size_t, size_t>
    _events(EventExtractor const & self,
            float                  minv,
            float                  maxv,
            int                    sz,
            float          const * data)
    {
        std::list<int> inds;
        auto test = [&](int & i)
        {
            if(data[i] >= minv && data[i] <= maxv)
            {
                inds.insert(inds.end(), i);
                if(inds.size() == self.mincount)
                {
                    if(std::abs(i-inds.front())+1 >= self.mincount*self.density)
                    {
                        i = inds.front();
                        inds.clear();
                        return false;
                    }
                    inds.erase(inds.begin());
                }
            }
            return true;
        };

        int first = 0u;
        while(first < sz && test(first))
            ++first;

        int second = sz-1;
        while(second >= first && test(second))
            --second;

        if(first > second)
            return {0u, 0u};
        return {size_t(first), size_t(second)+1u};
    }
}

Digitizer
CyclesDigitization::compute(float prec, cycles_t const & data) const
{
    std::vector<float> cycmin(data.size(),  std::numeric_limits<float>::max()),
                       cycmax(data.size(), -std::numeric_limits<float>::max());
    for(size_t i = 0u, ie = data.size(); i < ie; ++i)
    {
        auto cur = data[i].second;
        for(auto end = cur+data[i].first; cur != end; ++cur)
        {
            if(!std::isfinite(*cur))
                continue;
            if(cycmin[i] > *cur)
                cycmin[i] = *cur;
            if(cycmax[i] < *cur)
                cycmax[i] = *cur;
        }
    }

    using signalfilter::stats::percentile;
    auto ledge = percentile(cycmin.data(), cycmin.data()+data.size(), minv);
    auto redge = percentile(cycmax.data(), cycmax.data()+data.size(), maxv);
    auto ovr   = prec*overshoot;
    auto nbins = std::lround((redge-ledge+2.0f*ovr)/(precision*prec))+1l;
    auto delta = (redge-ledge+2.0f*ovr)/nbins;
    return {oversampling, prec, ledge-ovr, ledge-ovr+delta*nbins, (size_t) nbins};
}

float Digitizer::binwidth(bool ovr) const
{  
    auto bw = (maxedge-minedge)/(nbins +1u);
    return ovr ? bw/(1<<oversampling) : bw;
}

DigitizedData Digitizer::compute(size_t nframes, float const * data) const
{
    std::vector<int> out(nframes, -1);
    auto delta = 1.0f/binwidth(true);
    long thr   = (long) nbins;
    for(size_t i = 0u; i < nframes; ++i)
        if(std::isfinite(data[i]))
        {
            auto tmp = std::lround((data[i]-minedge)*delta);
            if(tmp >= 0l && (tmp>>oversampling) < thr)
                out[i] = (int) tmp;
        }

    return { oversampling, precision, 1.0f/binwidth(), nbins,  out };
}

std::vector<float> CycleProjection::compute(DigitizedData const & data) const
{
    if(data.nbins == 0u || data.digits.size() == 0u)
        return std::vector<float>(data.nbins, 1.0f);

    std::vector<size_t> hist; // Histogram of values
    if(dzratio > 0.0f)
        /* Histogram of values selected such that the derivative is
         * below a given threshold
         */
        switch(dzpattern)
        {
            case DzPattern::symmetric1:
                /* derivative is: (X(n+1)+X(n-1))/2 - X(n)
                 * where values i such that X(i) == -1 are silently ignored.
                 */
                hist = _apply<_Symm1Iterator>(*this, data);
                break;
            default:
                assert(false);
        }
    else
        /* Histogram of *all* values */
        hist = _apply<_DummyIterator>(*this, data);

    std::vector<float> weights;
    switch(weightpattern)
    {
        case WeightPattern::ones:
            /* Apply a moving sum to the histogram */
            weights = _toweights(*this, data, std::move(hist), [](auto) { return 1.0f; });
            break;
        case WeightPattern::inv:
            /* Normalize histogram values using a moving sum.
             * Maxima should all be reduced to 1.
             */
            weights = _toweights(*this, data, std::move(hist), [](auto x){ return 1.0f/x; });
            break;
        default:
            assert(false);
    }

    if(tsmoothingratio > 0.0f)
        /* Smooth the weights using proximate value both in time and z */
        return _tsmoothing(*this, data, weights);
    return weights;
}

std::vector<std::vector<float>> CycleProjection::compute(Digitizer const & project,
                                                         cycles_t  const & data) const
{
    std::vector<std::vector<float>> out;
    for(auto const & i: data)
    {
        auto tmp = project.compute(i.first, i.second);
        out.push_back(compute(tmp));
    }
    return out;
}

std::vector<float> ProjectionAggregator::compute(Digitizer                  const & project,
                                                 std::vector<float const *> const & data
                                                ) const
{
    std::vector<int> _(data.size(), 0);
    return compute(project, _, data);
}

std::vector<float> ProjectionAggregator::compute(Digitizer                  const & project,
                                                 std::vector<int>           const & delta,
                                                 std::vector<float const *> const & data
                                                ) const
{
    if(data.size() == 0u)
        return {};

    std::vector<float> out(data[0], data[0]+project.nbins);
    std::vector<float> cnt(project.nbins);
    int                sz = (int) cnt.size();


    /* Compute 2 histograms, sum and number of hits, using cycle histograms, each
     * with it's own bias.
     */
    for(int j = delta[0] < 0 ? -delta[0] : 0, ie = delta[0] < 0 ? sz : sz-delta[0]; j < ie; ++j)
        cnt[j] = out[j+delta[0]] > cycleminvalue ? 1.0f : 0.0f;
    for(size_t i = 1u, ie = data.size(); i < ie; ++i)
    {
        auto cur = data[i];
        auto dx  = delta[i];
        for(int j = dx < 0 ? -dx : 0, ie = dx < 0 ? sz : sz-dx; j < ie; ++j)
            if(cur[j+dx] > cycleminvalue)
            {
                out[j] += cur[j+dx];
                ++cnt[j];
            }
    }

    /* smooth the number of hits using a gaussian kernel */
    _smoothing(smoothinglen, _rnd(project, countsmoothingratio), cnt);

    /* normalize the sums using hits: we'll now have a estimation of
     * hybridisation rates
     */
    for(size_t j = 0u, je = cnt.size(); j < je; ++j)
        out[j] = cnt[j] > cyclemincount ? out[j]/cnt[j] : 0.0f;

    /* smooth the hybridization rates using a gaussian kernel */
    _smoothing(smoothinglen, _rnd(project, zsmoothingratio), out);
    return out;
}

std::pair<std::vector<float>, std::vector<float>>
CycleAlignment::compute(Digitizer                  const & project,
                        ProjectionAggregator       const & agg,
                        std::vector<float const *> const & data) const
{
    using signalfilter::stats::median;
    std::vector<int> out(data.size());
    auto             all = agg.compute(project, out, data);
    int              hw  = (int) _rnd(project, halfwindow);
    int              sz  = (int) project.nbins;
    for(size_t _ = 0u, ie = data.size(); _ < repeats; ++_)
    {
        for(size_t i = 0u; i < ie; ++i)
        {
            int   iminv = 0;
            float minv  = 0.0f;
            for(int dx = -hw; dx <= hw; ++dx)
            {
                float sumv = 0.0f;
                auto  cur  = data[i];
                for(int j = dx < 0 ? -dx : 0, je = dx < 0 ? sz : sz-dx; j < je; ++j)
                    sumv += all[j]*cur[j+dx];

                if(sumv > minv)
                {
                    iminv = dx;
                    minv  = sumv;
                }
            }
            out[i] = iminv;
        }

        auto tmp = out;
        auto med = median(tmp);
        if(med != 0)
            for(auto & i: out)
                i -= med;

        all = agg.compute(project, out, data);
    }

    std::vector<float> fout(out.size());
    auto               bw = project.binwidth();
    for(size_t i = 0u, ie = out.size(); i < ie; ++i)
        fout[i] = out[i]*bw;

    return {fout, all};
}

BeadProjectionData BeadProjection::compute(float prec, cycles_t const & data) const
{
    auto digit = digitize.compute(prec, data);
    auto hists = project.compute(digit, data);

    std::vector<float const *> tmp;
    for(auto const & i: hists)
        tmp.push_back(i.data());

    auto out   = align.compute(digit, aggregate, tmp); 
    auto bw    = digit.binwidth();
    auto peaks = find.compute(prec, digit.minedge, bw,
                              out.second.size(), out.second.data());
    return { out.second, out.first, digit.minedge, bw, peaks};
}

std::vector<std::vector<std::pair<size_t, size_t>>>
EventExtractor::compute(float            prec,
                        size_t           npks,
                        float    const * peaks,
                        float    const * bias,
                        cycles_t const & data) const
{
    std::vector<std::vector<std::pair<size_t, size_t>>> out(data.size());
    float dist = prec * distance;
    for(size_t icyc = 0u, ecyc = data.size(); icyc < ecyc; ++icyc)
        for(size_t ipk = 0u; ipk < npks; ++ipk)
            out[icyc].emplace_back(_events(
                        *this,
                        peaks[ipk]-dist+bias[icyc],
                        peaks[ipk]+dist+bias[icyc],
                        (int) data[icyc].first,
                        data[icyc].second));
    return out;
}
}}
