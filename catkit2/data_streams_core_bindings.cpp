#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include "DataStream.h"
#include "TimeStamp.h"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;

PYBIND11_MODULE(data_streams, m)
{
	py::class_<DataFrame>(m, "DataFrame")
		.def_property_readonly("id", [](const DataFrame &f)
			{
				return f.m_Id;
			})
		.def_property_readonly("timestamp", [](const DataFrame &f)
			{
				return f.m_TimeStamp;
			})
		.def_property_readonly("data", [](const DataFrame &f)
			{
				size_t item_size = GetSizeOfDataType(f.m_DataType);

				size_t ndim = 4;
				while (ndim > 0 && f.m_Dimensions[ndim - 1] == 1)
				{
					ndim--;
				}

				std::vector<py::ssize_t> shape;
				std::vector<py::ssize_t> strides;

				for (size_t i = 0; i < ndim; ++i)
				{
					shape.push_back(f.m_Dimensions[i]);
				}
				for (int i = int(ndim - 1); i >= 0; --i)
				{
					size_t stride = 1;
					for (int j = int(ndim - 1); j > i; --j)
						stride *= (unsigned short) shape[j];
					strides.push_back(item_size * stride);
				}

				return py::array(
					GetDataTypeAsString(f.m_DataType),
					shape,
					f.m_Data,
					py::none()
					);
			});

	m.def("get_timestamp", &GetTimeStamp);

	m.def("get_dataframe", []()
		{
			DataFrame frame;
			frame.m_Id = 5;
			frame.m_TimeStamp = GetTimeStamp();

			frame.m_Dimensions[0] = 15;
			frame.m_Dimensions[1] = frame.m_Dimensions[2] = frame.m_Dimensions[3] = 1;

			frame.m_DataType = DataType::DT_UINT16;

			frame.m_Data = new char[30];
			unsigned short *data = (unsigned short *) frame.m_Data;
			for (size_t i = 0; i < 15; ++i)
				data[i] = (unsigned short) i;

			return frame;
		});

#ifdef VERSION_INFO
	m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
	m.attr("__version__") = "dev";
#endif
}
