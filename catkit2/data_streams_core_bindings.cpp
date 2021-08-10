#include <pybind11/pybind11.h>

#include "DataStream.h"
#include "TimeStamp.h"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;

PYBIND11_MODULE(data_streams, m)
{
	py::class_<DataFrame>(m, "DataFrame");

	m.def("get_timestamp", &GetTimeStamp);

#ifdef VERSION_INFO
	m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
	m.attr("__version__") = "dev";
#endif
}
