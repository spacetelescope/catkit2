#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11_json/pybind11_json.hpp>

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

	void Open() override
	{
		py::gil_scoped_acquire acquire;
		PYBIND11_OVERRIDE_NAME(void, Module, "open", Open);
	}

	void Main() override
	{
		py::gil_scoped_acquire acquire;
		PYBIND11_OVERRIDE_NAME(void, Module, "main", Main);
	}

	void Close() override
	{
		py::gil_scoped_acquire acquire;
		PYBIND11_OVERRIDE_NAME(void, Module, "close", Close);
	}

	void ShutDown() override
	{
		py::gil_scoped_acquire acquire;
		PYBIND11_OVERRIDE_NAME(void, Module, "shut_down", ShutDown);
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
		.def("run", &Module::Run, py::call_guard<py::gil_scoped_release>())
		.def("open", &Module::Open)
		.def("main", &Module::Main)
		.def("close", &Module::Close)
		.def("shut_down", &Module::ShutDown)
		.def("register_property", &PublicistModule::RegisterProperty)
		.def("register_command", &PublicistModule::RegisterCommand)
		.def("register_data_stream", &PublicistModule::RegisterDataStream);

	py::class_<Command, std::shared_ptr<Command>>(m, "Command")
		.def(py::init([](std::string name, py::object command)
			{
				return std::make_shared<Command>(name, [command](const nlohmann::json &arguments)
				{
					py::gil_scoped_acquire acquire;
					py::dict kwargs = py::cast(arguments);
					return command(**kwargs);
				});
			}))
		.def_property_readonly("name", &Command::GetName);

	py::class_<Property, std::shared_ptr<Property>>(m, "Property")
		.def(py::init<std::string, Property::Getter, Property::Setter>(),
			py::arg("name"),
			py::arg("getter") = nullptr,
			py::arg("setter") = nullptr)
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

				std::vector<py::ssize_t> shape;
				for (size_t i = 0; i < f.m_NumDimensions; ++i)
				{
					shape.push_back(f.m_Dimensions[i]);
				}

				std::vector<py::ssize_t> strides;
				for (int i = 0; i < f.m_NumDimensions; ++i)
				{
					size_t stride = item_size;

					for (int j = int(f.m_NumDimensions - 1); j > i; --j)
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
		.def_static("create", [](std::string &stream_name, std::string &module_name, std::string &type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
		{
			DataType dtype = GetDataTypeFromString(type);
			return DataStream::Create(stream_name, module_name, dtype, dimensions, num_frames_in_buffer);
		})
		.def_static("open", [](std::string &stream_name, std::string &module_name)
		{
			return DataStream::Open(stream_name, module_name);
		})
		.def("request_new_frame", &DataStream::RequestNewFrame)
		.def("submit_frame", &DataStream::SubmitFrame)
		.def("get_frame", [](DataStream &s, size_t id, bool wait, unsigned long wait_time_in_ms)
		{
			return s.GetFrame(id, wait, wait_time_in_ms, []()
			{
				py::gil_scoped_acquire acquire;
				if (PyErr_CheckSignals() != 0)
					throw py::error_already_set();
			});
		}, py::arg("id"), py::arg("wait") = true, py::arg("wait_time_in_ms") = INFINITE, py::call_guard<py::gil_scoped_release>())
		.def("get_next_frame", [](DataStream &s, bool wait, unsigned long wait_time_in_ms)
		{
			return s.GetNextFrame(wait, wait_time_in_ms, []()
			{
				py::gil_scoped_acquire acquire;
				if (PyErr_CheckSignals() != 0)
					throw py::error_already_set();
			});
		}, py::arg("wait") = true, py::arg("wait_time_in_ms") = INFINITE, py::call_guard<py::gil_scoped_release>())
		.def("get_latest_frame", &DataStream::GetLatestFrame, py::call_guard<py::gil_scoped_release>())
		.def_property("dtype", [](DataStream &s)
		{
			return py::dtype(GetDataTypeAsString(s.GetDataType()));
		},
		[](DataStream &s, py::object dtype)
		{
			DataType stream_dtype = GetDataTypeFromString(py::cast<py::str>(py::dtype::from_args(std::move(dtype))));

			if (stream_dtype == DataType::DT_UNKNOWN)
				throw std::invalid_argument("The datatype is unknown.");

			s.SetDataType(stream_dtype);
		})
		.def_property("shape", &DataStream::GetDimensions, &DataStream::SetDimensions)
		.def_property("num_frames_in_buffer", &DataStream::GetNumFramesInBuffer, &DataStream::SetNumFramesInBuffer)
		.def("update_parameters", [](DataStream &s, py::object dtype, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
		{
			DataType stream_dtype = GetDataTypeFromString(py::cast<py::str>(py::dtype::from_args(std::move(dtype))));

			if (stream_dtype == DataType::DT_UNKNOWN)
				throw std::invalid_argument("The datatype is unknown.");

			s.UpdateParameters(stream_dtype, dimensions, num_frames_in_buffer);
		})
		.def_property_readonly("version", &DataStream::GetVersion)
		.def_property_readonly("stream_name", &DataStream::GetStreamName)
		.def_property_readonly("module_name", &DataStream::GetModuleName)
		.def_property_readonly("time_created", &DataStream::GetTimeCreated)
		.def_property_readonly("creator_pid", &DataStream::GetCreatorPID)
		.def("is_frame_available", &DataStream::IsFrameAvailable)
		.def("will_frame_be_available", &DataStream::WillFrameBeAvailable)
		.def_property_readonly("newest_available_frame_id", &DataStream::GetNewestAvailableFrameId)
		.def_property_readonly("oldest_available_frame_id", &DataStream::GetOldestAvailableFrameId)
		.def_property("buffer_handling_mode", &DataStream::GetBufferHandlingMode, &DataStream::SetBufferHandlingMode);

	py::enum_<BufferHandlingMode>(m, "BufferHandlingMode")
		.value("NEWEST_ONLY", BM_NEWEST_ONLY)
		.value("OLDEST_FIRST_OVERWRITE", BM_OLDEST_FIRST_OVERWRITE);

	m.def("get_timestamp", &GetTimeStamp);
	m.def("convert_timestamp_to_string", &ConvertTimestampToString);

#ifdef VERSION_INFO
	m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
	m.attr("__version__") = "dev";
#endif
}
