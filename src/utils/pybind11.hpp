#include <string>
#include <vector>
#include <valarray>
#include <type_traits>
#include <boost/preprocessor/stringize.hpp>
#include <boost/preprocessor/seq.hpp>
#include <boost/preprocessor/seq/cat.hpp>
#include <boost/preprocessor/seq/for_each.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#define DPX_TO_PP(_, CLS, ATTR) , dpx::pyinterface::pp(BOOST_PP_STRINGIZE(ATTR), &CLS::ATTR)
#define DPX_PY2C(CLS, ATTRS) \
    _defaults<CLS>(mod, #CLS, doc BOOST_PP_SEQ_FOR_EACH(DPX_TO_PP, CLS, ATTRS));
#define DPX_ADD_API(cls, CLS, ATTRS) \
    dpx::pyinterface::addapi<CLS>(cls BOOST_PP_SEQ_FOR_EACH(DPX_TO_PP, CLS, ATTRS));
#define DPX_WRAP(CLS, ATTRS) \
    py::class_<CLS> cls(mod, #CLS, doc);\
    dpx::pyinterface::addapi<CLS>(cls BOOST_PP_SEQ_FOR_EACH(DPX_TO_PP, CLS, ATTRS));

namespace dpx { namespace pyinterface {
    namespace py = pybind11;
    template <typename T>
    using ndarray = py::array_t<T, py::array::c_style>;

    template <typename T, typename K>
    inline ndarray<T> toarray2d(K shape, T const * ptr)
    {
        auto out = pybind11::array_t<T>(shape, {long(shape[1]*sizeof(T)), long(sizeof(T))});
        std::copy(ptr, ptr+shape[1]*shape[0], out.mutable_data());
        return out;
    }

    template <typename T, typename K>
    inline ndarray<T> toarray2d(K && shape, T const * ptr)
    {
        auto out = pybind11::array_t<T>(std::move(shape),
                                        {long(shape[1]*sizeof(T)), long(sizeof(T))});
        std::copy(ptr, ptr+shape[1]*shape[0], out.mutable_data());
        return out;
    }

    template <typename T>
    inline ndarray<T> toarray(size_t sz, T const *ptr)
    {
        auto out = pybind11::array_t<T>(sz);
        std::copy(ptr, ptr+sz, out.mutable_data());
        return out;
    }

    template <typename T>
    inline ndarray<T> toarray(std::vector<T> const & ptr)
    { return toarray(ptr.size(), ptr.data()); }

    template <typename T>
    inline ndarray<T> toarray(std::valarray<T> const & ptr)
    { return toarray(ptr.size(), &ptr[0]); }

    template <typename T>
    inline ndarray<T> toarray(std::vector<T> const && ptr)
    { return toarray(ptr.size(), ptr.data()); }

    template <typename T>
    inline ndarray<T> toarray(std::valarray<T> const && ptr)
    { return toarray(ptr.size(), &ptr[0]); }

    struct Check
    {
        bool err = false;
        bool operator () ();
    };

#   ifdef _MSC_VER
#       pragma warning( push )
#       pragma warning( disable : 4800)
#   endif
    inline bool Check::operator () () { return !(err || (err = PyErr_Occurred())); };
#   ifdef _MSC_VER
#       pragma warning( pop )
#   endif

    template <typename T, typename K>
    struct PyPair
    {
        const char * name;
        K       T::* attr;
    };

    template <typename T, typename K>
    inline constexpr PyPair<T, K> pp(char const * name, K T::*attr) { return {name, attr}; }

    template <typename T>
    inline void get(T & inst, char const * name, py::dict & kwa)
    {
        if(kwa.contains(name))
            inst = kwa[name].cast<T>();
    }

    template <typename T>
    inline void get(T const & inst, char const * name, py::dict & kwa)
    { kwa[name] = inst; }

    template <typename T, typename TT, typename K>
    inline int get(T const & inst, PyPair<TT, K> const & arg, py::dict & kwa)
    { kwa[arg.name] = inst.*(arg.attr); return 0; }

    template <typename T, typename TT, typename K>
    inline int get(T & inst, PyPair<TT, K> const & arg, py::dict const & kwa)
    { 
        if(kwa.contains(arg.name))
            inst.*(arg.attr) = kwa[arg.name].template cast<K>();
        return 0;
    }

    inline void unpack(...) {}

    template <typename T, typename ...Args>
    inline void mapto(T && fcn, Args ... args) {  unpack(fcn(args)...); }

    template <typename T, typename ...Args> 
    inline void get(T & inst, py::dict const & kwa, Args const &... args)
    { unpack(get(inst, args, kwa)...); }

    template <typename T, typename ...Args> 
    inline void get(T const & inst, py::dict & kwa, Args const &... args)
    { unpack(get(inst, args, kwa)...); }

    template <typename T, typename ...Args> 
    inline py::dict config(T const & inst, Args const &... args)
    { 
        py::dict d;
        get(inst, d, args...); 
        return d;
    }

    template <typename T, typename ...Args> 
    inline std::unique_ptr<T> create(py::dict const & kwa, Args const & ... args)
    {
        std::unique_ptr<T> self(new T());
        get(*self, kwa, args...);
        return self;
    }

    template <typename T>
    bool equals(py::object const & a, py::object const & b)
    {
        if(!a.attr("__class__").is(b.attr("__class__")))
            return false;
        return std::memcmp(a.cast<T*>(), b.cast<T*>(), sizeof(T)) == 0;
    }

    template <typename T, typename ...Args>
    inline void addapi(py::class_<T> & cls, Args && ... els)
    {
        cls.def(py::init(    [els...](py::kwargs d) { return create<T>(d,  els...); }));
        cls.def("configure", [els...](T const & me) { return config<T>(me, els...); });
        cls.def(py::pickle(  [els...](T const & me) { return config<T>(me, els...); },
                             [els...](py::dict   d) { return create<T>(d,  els...); }));
        cls.def("__eq__",    &equals<T>);
        mapto([&cls](auto x){ cls.def_readwrite(x.name, x.attr); return 0; }, els...);
    }
}}
