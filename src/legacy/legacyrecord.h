#pragma once
#include <cstdint>
#include <cstring>
#include <string>
#include <exception>
#include <vector>
#include <map>

namespace legacy
{
    struct      gen_record;
    gen_record* load    (char *fullfile);
    int         freegr  (gen_record *g_r);

    struct GenRecord
    {
        GenRecord()                  = default;
        GenRecord(GenRecord const &) = delete;
        GenRecord(std::string x, int nbeads = -1)    : GenRecord() { open(x, nbeads); }
        ~GenRecord() { close(); }

        void open(std::string x, int nbeads = -1, int start = -1, int stop = -1, int nphases = -1);

        void close()
        { auto x = _ptr; _ptr   = nullptr; freegr(x); }

        size_t nbeads   () const;
        size_t nrecs    () const;
        int    cyclemin () const;
        int    cyclemax () const;
        size_t ncycles  () const;
        size_t nphases  () const;
        std::tuple<float, float, float, float> dimensions() const;
        bool   readcalib(int im, std::string fname) const;

        bool   islost(int i) const;
        void   cycles(int *)            const;
        void   t     (int *)            const;
        void   status(int *)            const;
        void   zmagcmd(float *)         const;
        void   zmag  (float *)          const;
        void   rot   (float *)          const;
        void   bead  (size_t, float *)  const;
        void   xbead (size_t, float *)  const;
        void   ybead (size_t, float *)  const;
        void   xbeaderr (size_t, float *)  const;
        void   ybeaderr (size_t, float *)  const;
        void   zbeaderr (size_t, float *)  const;
        void   cycles(std::vector<int>    & x) const { x.resize(nphases()*ncycles()); cycles(x.data()); }
        void   t     (std::vector<int>    & x) const { x.resize(nrecs());   t     (x.data()); }
        void   status(std::vector<int>    & x) const { x.resize(nrecs());   status(x.data()); }
        void   zmagcmd(std::vector<float>  & x) const { x.resize(nrecs());  zmagcmd(x.data()); }
        void   zmag  (std::vector<float>  & x) const { x.resize(nrecs());   zmag  (x.data()); }
        void   rot   (std::vector<float>  & x) const { x.resize(nrecs());   rot   (x.data()); }
        void   bead  (size_t i, std::vector<float> & x) const
        { x.resize(nrecs()); bead(i, x.data()); }
        void   xbead (size_t i, std::vector<float> & x) const
        { x.resize(nrecs()); xbead(i, x.data()); }
        void   ybead (size_t i, std::vector<float> & x) const
        { x.resize(nrecs()); ybead(i, x.data()); }

        bool   readfov(int &nx, int &ny, int &dt, void *& ptr);
        void   destroyfov(int dt, void *& ptr);
        std::map<int, std::tuple<float, float, float>> pos()  const;

        std::vector<std::vector<std::pair<int, float> > > temperatures() const;
        std::vector<std::vector<float>>                   vcap        () const;

        std::vector<int  >  t     ()         const { decltype(t   ())   x; t   (x);     return x; }
        std::vector<int  >  status()         const { decltype(status()) x; status(x);   return x; }
        std::vector<float>  zmagcmd()        const { decltype(zmagcmd()) x; zmagcmd(x); return x; }
        std::vector<float>  zmag  ()         const { decltype(zmag())   x; zmag(x);     return x; }
        std::vector<float>  rot   ()         const { decltype(rot ())   x; rot (x);     return x; }
        std::vector<float>  bead  (size_t i) const { decltype(bead(0))  x; bead(i, x);  return x; }
        std::vector<float>  xbead (size_t i) const { decltype(bead(0))  x; xbead(i, x); return x; }
        std::vector<float>  ybead (size_t i) const { decltype(bead(0))  x; ybead(i, x); return x; }
        std::vector<float>  bead  (size_t i, int tpe) const;
        std::vector<int>    cycles()         const { decltype(cycles()) x; cycles(x);   return x; }

        float       camerafrequency() const;
        std::string instrumentname() const;
        bool   sdi() const;

        private:
            template <typename T>
            void _get(T **, T, T, T *) const;
            gen_record *        _ptr = nullptr;
            std::string         _name;
    };

    struct TrackIOException: public std::exception
    {
        template <typename T>
        TrackIOException(T t) : _msg(t) {}
        char const * what() const throw() override { return _msg.c_str(); }

        private:
            std::string _msg;
    };

}
