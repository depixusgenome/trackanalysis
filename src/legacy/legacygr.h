#pragma once
#include <vector>
#include <string>
namespace legacy
{
    struct DsData
    {
        std::string        title;
        std::vector<float> xd;
        std::vector<float> yd;
    };

    struct GrData
    {
        std::string         title;
        std::vector<DsData> items;
    };

    GrData readgr(std::string fname);
}
