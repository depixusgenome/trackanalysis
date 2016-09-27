#pragma once
#include <cstdint>
#include <cstring>
#include <string>
#include <exception>
#include <vector>

namespace legacy
{
    struct      gen_record;
    gen_record* load    (char *fullfile);
    int         freegr  (gen_record *g_r);

    struct GenRecord
    {
        GenRecord()                  = default;
        GenRecord(GenRecord const &) = delete;
        GenRecord(std::string x)    : GenRecord() { open(x); }
        ~GenRecord() { close(); }

        void open(std::string x)
        {
            close();
            char tmp[2048];
            strncpy(tmp, x.c_str(), sizeof(tmp));
            _ptr = load(tmp);
        }

        void close()
        { auto x = _ptr; _ptr   = nullptr; freegr(x); }

        size_t nbeads   () const;
        size_t nrecs    () const;
        int    cyclemin () const;
        int    cyclemax () const;
        size_t ncycles  () const;
        size_t nphases  () const;
        bool   islost(int i) const;
        void   cycles(int *)           const;
        void   t     (int *)            const;
        void   zmag  (float *)          const;
        void   bead  (size_t, float *)  const;
        void   cycles(std::vector<int>    & x) const { x.resize(nphases()*ncycles()); cycles(x.data()); }
        void   t     (std::vector<int>    & x) const { x.resize(nrecs());   t     (x.data()); }
        void   zmag  (std::vector<float>  & x) const { x.resize(nrecs());   zmag  (x.data()); }
        void   bead  (size_t i, std::vector<float> & x) const
        { x.resize(nrecs()); bead(i, x.data()); }

        std::vector<float>  bead  (size_t i) const { decltype(bead(0))  x; bead(i, x);  return x; }
        std::vector<float>  zmag  ()         const { decltype(zmag())   x; zmag(x);     return x; }
        std::vector<int  >  t     ()         const { decltype(t   ())   x; t   (x);     return x; }
        std::vector<int>    cycles()         const { decltype(cycles()) x; cycles(x);   return x; }

        float  camerafrequency() const;

        private:
            gen_record * _ptr = nullptr;
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
