#include <list>
#include <algorithm>
#include "peakcalling/optimize.hpp"
#include "peakcalling/listmatching.h"
namespace peakcalling { namespace match
{
    namespace
    {
        template <typename K0, typename K1>
        void _matched( float const * bead1
                     , size_t        size1
                     , float const * bead2
                     , size_t        size2
                     , float         sigma
                     , K0            add
                     , K1            discard
                     )
        {
            struct _MInfo
            {
                bool   color;
                size_t ind;
                float  pos;
            };

            using list_t  = std::list<_MInfo>;

            auto pX   = [&](size_t i) -> _MInfo
                        { return {true,  i, bead1[i]}; };
            auto pY   = [&](size_t i) -> _MInfo
                        { return {false, i, bead2[i]}; };

            auto endoflist  = [&](auto const &lst, auto const & minc)
                            {
                                if(lst.size() == 0)
                                    return false;

                                auto const & back = lst.back();
                                return minc.color == back.color
                                    || back.pos < minc.pos - sigma;
                            };
            auto findbest   = [](auto const & cur)
                            {
                                auto val  = std::numeric_limits<float>::max();
                                auto best = cur.end();
                                auto lpos = cur.front().pos;
                                for(auto it = std::next(cur.begin())
                                       , e  = cur.end(); it != e; ++it)
                                {
                                    if(it->pos-lpos < val)
                                    {
                                        best = it;
                                        val  = it->pos-lpos;
                                    }
                                    lpos = it->pos;
                                }
                                return best;
                            };
            auto empty      = [&](auto && cur)
                            {
                                auto left = std::move(cur);

                                std::list<list_t> stack;
                                while(left.size() > 1 || stack.size() > 0)
                                {
                                    if(left.size() <= 1)
                                    {
                                        if(     left.size() == 1
                                            &&  discard(left.front())
                                          ) return true;

                                        left = std::move(stack.back());
                                        stack.pop_back();
                                    }

                                    auto best = findbest(left);
                                    auto prev = std::prev(best);
                                    if(best->color)
                                        add(*best, *prev);
                                    else
                                        add(*prev, *best);

                                    list_t right;
                                    right.splice(right.end(), left, ++best, left.end());
                                    if(right.size() > 1)
                                        stack.emplace_back(right);

                                    left.pop_back();
                                    left.pop_back();
                                }
                                return false;
                            };

            size_t  iX = 0, iY = 0;
            _MInfo  minc{true, 0, 0.f};
            list_t curlist;

            if(size1 > 0 && size2 > 0)
            {
                for(auto maxc = pY(0); iX < size1 && iY < size2; minc.color ? ++iX : ++iY)
                {
                    minc = minc.color ? pX(iX) : pY(iY);
                    if(minc.pos > maxc.pos)
                        std::swap(minc, maxc);

                    if(endoflist(curlist, minc) && empty(curlist))
                        return;

                    curlist.push_back(minc);
                }

                minc = iX == size1 ? pY(iY++) : pX(iX++);
                if(!endoflist(curlist, minc))
                    curlist.push_back(minc);
            }

            while(iX < size1)
                if(discard(pX(iX++)))
                    return;
            while(iY < size2)
                if(discard(pY(iY++)))
                    return;

            empty(curlist);
        }
    }

    Output compute( float          sigma
                  , float const *  bead1
                  , size_t         size1
                  , float const *  bead2
                  , size_t         size2
                  )
    {
        size_t cnt = 0;
        std::vector<size_t> out(size1, std::numeric_limits<size_t>::max());
        _matched(bead1, size1, bead2, size2, sigma,
                 [&](auto const & a, auto const & b)
                    { out[a.ind] = b.ind; ++cnt; },
                 [](...) { return false; });

        Output m(cnt*2);
        for(size_t i = 0, j = 0, e = out.size(); i < e; ++i)
            if(out[i] != std::numeric_limits<size_t>::max())
            {
                m[j++] = i;
                m[j++] = out[i];
            }
        return m;
    }

    size_t nfound( float          sigma
                 , float const *  bead1
                 , size_t         size1
                 , float const *  bead2
                 , size_t         size2
                 )
    {
        size_t cnt = 0;
        _matched(bead1, size1, bead2, size2, sigma,
                 [&](auto const &, auto const &) { ++cnt; },
                 [](...) { return false; });
        return cnt;
    }

    std::tuple<double, double, double, size_t> distance( float          sigma
                                                       , float          stretch
                                                       , float          bias
                                                       , float const *  bead1
                                                       , size_t         size1
                                                       , float const *  bead2
                                                       , size_t         size2
                                                       )
    {
        double res   = 0.;
        double grads = 0.;
        double gradb = 0.;
        size_t cnt   = 0;
        std::vector<float> conv(size2);
        for(size_t i = size_t(0); i < size2; ++i)
            conv[i] = bead2[i] * stretch + bias;

        _matched(bead1, size1, conv.data(), size2, sigma,
                 [&](auto const & a, auto const & b)
                    {
                        auto t = a.pos - b.pos;
                        res   += t*t;
                        grads -= bead2[b.ind]*t;
                        gradb -= t;
                        ++cnt;
                    },
                 [](...) { return false; });

        if(cnt == 0)
            return std::make_tuple(size2+size1+1.0, 0., 0., cnt);

        double norm = 1./(sigma*sigma);
        return std::make_tuple(size2+size1-2*cnt + res*norm,
                               2.0*grads*norm,
                               2.0*gradb*norm,
                               cnt);
    }

    namespace
    {
        double  _compute(unsigned, double const * x, double * g, void * d)
        {
            auto const & cf = *((optimizer::NLOptCall<> const *) d);
            auto res = distance(cf.params->sigma, x[0], x[1],
                                cf.beads[0], cf.sizes[0],
                                cf.beads[1], cf.sizes[1]);
            g[0] = std::get<1>(res);
            g[1] = std::get<2>(res);
            return std::get<0>(res);
        }
    }

    optimizer::Output optimize (Parameters const & cf,
                                float const * bead1, size_t size1,
                                float const * bead2, size_t size2)
    { return optimizer::optimize(cf, bead1, nullptr, size1, bead2, nullptr, size2, _compute); }
}}
