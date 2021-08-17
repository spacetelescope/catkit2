#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "DataStream.h"
#include "TimeStamp.h"
//#include "Module.h"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;

PYBIND11_MODULE(bindings, m)
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
				for (size_t i = 0; i < ndim; ++i)
				{
					shape.push_back(f.m_Dimensions[i]);
				}

				std::vector<py::ssize_t> strides;
				for (int i = 0; i < ndim; ++i)
				{
					size_t stride = item_size;

					for (int j = int(ndim - 1); j > i; --j)
						stride *= shape[j];

					strides.push_back(stride);
				}

				return py::array(
					GetDataTypeAsString(f.m_DataType),
					shape,
					strides,
					f.m_Data,
					py::none()
					);
			});

	py::class_<DataStream, std::shared_ptr<DataStream>>(m, "DataStream")
		.def_static("create", [](std::string &name, std::string &type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
		{
			DataType dtype = GetDataTypeFromString(type);
			return DataStream::Create(name, dtype, dimensions, num_frames_in_buffer);
		})
		.def_static("open", [](std::string &name)
		{
			return DataStream::Open(name);
		})
		.def("request_new_frame", &DataStream::RequestNewFrame)
		.def("submit_frame", &DataStream::SubmitFrame)
		.def("get_frame", [](DataStream &s, size_t id, bool wait, unsigned long wait_time_in_ms)
		{
			return s.GetFrame(id, wait, wait_time_in_ms, []()
			{
				if (PyErr_CheckSignals() != 0)
					throw py::error_already_set();
			});
		}, py::arg("id"), py::arg("wait") = true, py::arg("wait_time_in_ms") = INFINITE)
		.def("get_next_frame", [](DataStream &s, bool wait, unsigned long wait_time_in_ms)
		{
			return s.GetNextFrame(wait, wait_time_in_ms, []()
			{
				if (PyErr_CheckSignals() != 0)
					throw py::error_already_set();
			});
		}, py::arg("wait") = true, py::arg("wait_time_in_ms") = INFINITE)
		.def_property_readonly("dtype", [](DataStream &s)
		{
			return py::dtype(GetDataTypeAsString(s.GetDataType()));
		})
		.def_property_readonly("shape", &DataStream::GetDimensions)
		.def_property_readonly("version", &DataStream::GetVersion)
		.def_property_readonly("name", &DataStream::GetName)
		.def_property_readonly("time_created", &DataStream::GetTimeCreated)
		.def_property_readonly("creator_pid", &DataStream::GetCreatorPID)
		.def("is_frame_available", &DataStream::IsFrameAvailable)
		.def("will_frame_be_available", &DataStream::WillFrameBeAvailable)
		.def_property_readonly("newest_available_frame_id", &DataStream::GetNewestAvailableFrameId)
		.def_property_readonly("oldest_available_frame_id", &DataStream::GetOldestAvailableFrameId);

	m.def("get_timestamp", &GetTimeStamp);
	m.def("convert_timestamp_to_string", &ConvertTimestampToString);

	m.def("get_dataframe", []()
		{
			DataFrame frame;
			frame.m_Id = 5;
			frame.m_TimeStamp = GetTimeStamp();

			frame.m_Dimensions[0] = frame.m_Dimensions[1] = 4;
			frame.m_Dimensions[2] = frame.m_Dimensions[3] = 1;

			frame.m_DataType = DataType::DT_UINT16;

			frame.m_Data = new char[32];
			unsigned short *data = (unsigned short *) frame.m_Data;
			for (size_t i = 0; i < 16; ++i)
				data[i] = (unsigned short) i;

			return frame;
		});

#ifdef VERSION_INFO
	m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
	m.attr("__version__") = "dev";
#endif
}
