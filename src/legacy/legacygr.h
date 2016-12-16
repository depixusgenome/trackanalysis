#pragma once
#include <string>
namespace legacy
{
    struct one_plot;
    struct GrData
    {
        GrData(std::string fname);
        ~GrData();
        bool        isnone()            const { return _op == nullptr; }
        std::string title()             const;
        std::string title(size_t)       const;
        size_t      size ()             const;
        size_t      size (bool, size_t) const;
        float *     data (bool, size_t) const;
        private:
            one_plot *_op;
    };

    struct one_image;
    struct ImData
    {
        ImData(std::string fname);
        ~ImData();
        bool                      isnone ()       const { return _op == nullptr; }
        std::string               title  ()       const;
        std::pair<size_t,size_t>  dims   ()       const;
        bool                      isfloat()       const;
        bool                      ischar ()       const;
        void                      data   (void *) const;
        private:
            one_image *_op;
    };
}
