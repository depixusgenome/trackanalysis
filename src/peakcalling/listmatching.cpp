#include <list>
#include <algorithm>
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
}}
