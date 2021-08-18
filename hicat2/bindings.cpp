#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "DataStream.h"
#include "TimeStamp.h"
#include "Module.h"
#include "Command.h"
#include "Property.h"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;

class TrampolineModule : public Module
{
public:
	using Module::Module;

	void ShutDown() override
	{
		PYBIND11_OVERRIDE_NAME(void, Module, "shut_down", ShutDown,);
	}
};

class PublicistModule : public Module
{
public:
	using Module::RegisterProperty;
	using Module::RegisterCommand;
	using Module::RegisterDataStream;
};

PYBIND11_MODULE(bindings, m)
{
	py::class_<Module, TrampolineModule>(m, "Module")
		.def(py::init<std::string, int>())
		.def_property_readonly("name", &Module::GetName)
		.def("shut_down", &Module::ShutDown)
		.def("register_property", &PublicistModule::RegisterProperty)
		.def("register_command", &PublicistModule::RegisterCommand)
		.def("register_data_stream", &PublicistModule::RegisterDataStream);

	py::class_<Command>(m, "Command")
		.def(py::init<std::string, Command::CommandFunction>())
		.def_property_readonly("name", &Command::GetName);

	py::class_<Property>(m, "Property")
		.def(py::init<std::string, Property::Getter, Property::Setter>())
		.def_property_readonly("name", &Property::GetName);

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

#ifdef VERSION_INFO
	m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
	m.attr("__version__") = "dev";
#endif
}
