#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11_json/pybind11_json.hpp>

#include "DataStream.h"
#include "TimeStamp.h"
#include "Service.h"
#include "Command.h"
#include "Property.h"
#include "Log.h"
#include "LogConsole.h"
#include "LogPublish.h"

#define STRINGIFY(x) #x
#define MACRO_STRINGIFY(x) STRINGIFY(x)

namespace py = pybind11;

class TrampolineService : public Service
{
public:
	using Service::Service;

	void Open() override
	{
		py::gil_scoped_acquire acquire;
		PYBIND11_OVERRIDE_NAME(void, Service, "open", Open);
	}

	void Main() override
	{
		py::gil_scoped_acquire acquire;
		PYBIND11_OVERRIDE_NAME(void, Service, "main", Main);
	}

	void Close() override
	{
		py::gil_scoped_acquire acquire;
		PYBIND11_OVERRIDE_NAME(void, Service, "close", Close);
	}

	void ShutDown() override
	{
		py::gil_scoped_acquire acquire;
		PYBIND11_OVERRIDE_NAME(void, Service, "shut_down", ShutDown);
	}
};

py::array GetDataFromDataFrame(DataFrame &f)
{
	size_t item_size = GetSizeOfDataType(f.m_DataType);

	std::vector<py::ssize_t> shape;
	for (size_t i = 0; i < f.m_NumDimensions; ++i)
	{
		shape.push_back(f.m_Dimensions[i]);
	}

	auto strides = py::detail::c_strides(shape, item_size);

	return py::array(
		py::dtype(GetDataTypeAsString(f.m_DataType)),
		shape,
		strides,
		f.m_Data,
		py::none()
		);
}

PYBIND11_MODULE(bindings, m)
{
	py::class_<Service, TrampolineService>(m, "Service")
		.def(py::init<std::string, std::string, int>())
		.def_property_readonly("name", &Service::GetServiceName)
		.def_property_readonly("configuration", &Service::GetConfiguration)
		.def("run", &Service::Run, py::call_guard<py::gil_scoped_release>())
		.def("open", &Service::Open)
		.def("main", &Service::Main)
		.def("close", &Service::Close)
		.def("shut_down", &Service::ShutDown)
		.def("make_property", &Service::MakeProperty,
			py::arg("name"),
			py::arg("getter") = nullptr,
			py::arg("setter") = nullptr)
		.def("make_command", [](Service &service, std::string name, py::object command)
		{
			return service.MakeCommand(name, [command](const nlohmann::json &arguments)
			{
				py::gil_scoped_acquire acquire;
				py::dict kwargs = py::cast(arguments);
				return command(**kwargs);
			});
		})
		.def("make_data_stream", [](Service &service, std::string stream_name, std::string type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
		{
			DataType dtype = GetDataTypeFromString(type);
			return service.MakeDataStream(stream_name, dtype, dimensions, num_frames_in_buffer);
		});

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
		.def_property_readonly("data", &GetDataFromDataFrame);

	py::class_<DataStream, std::shared_ptr<DataStream>>(m, "DataStream")
		.def_static("create", [](std::string &stream_name, std::string &service_name, std::string &type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
		{
			DataType dtype = GetDataTypeFromString(type);
			return DataStream::Create(stream_name, service_name, dtype, dimensions, num_frames_in_buffer);
		})
		.def_static("open", [](std::string &stream_id)
		{
			return DataStream::Open(stream_id);
		})
		.def("request_new_frame", &DataStream::RequestNewFrame)
		.def("submit_frame", &DataStream::SubmitFrame)
		.def("submit_data", [](DataStream &s, py::buffer data)
		{
			auto buffer_info = data.request();

			// Check if data has the right dtype.
			if (GetDataTypeAsString(s.GetDataType()) != buffer_info.format)
				throw std::runtime_error("Incompatible array dtype.");

			// Check if data has the right shape.
			size_t ndim = s.GetNumDimensions();

			if (ndim != buffer_info.ndim)
				throw std::runtime_error("Incompatible array shape.");

			std::vector<py::ssize_t> shape;
			for (size_t i = 0; i < ndim; ++i)
			{
				shape.push_back(s.GetDimensions()[i]);
			}

			for (size_t i = 0; i < ndim; i++)
			{
				if (shape[i] != buffer_info.shape[i])
					throw std::runtime_error("Incompatible array shape.");
			}

			// Check if data is C continguous.
			auto strides = py::detail::c_strides(shape, GetSizeOfDataType(s.GetDataType()));

			for (size_t i = 0; i < ndim; i++)
			{
				if (strides[i] != buffer_info.strides[i])
					throw std::runtime_error("Input array must be C continguous.");
			}

			// All checks are complete. Let's copy/submit the raw data.
			s.SubmitData(buffer_info.ptr);
		})
		.def("get_frame", [](DataStream &s, size_t id, unsigned long wait_time_in_ms)
		{
			return s.GetFrame(id, wait_time_in_ms, []()
			{
				py::gil_scoped_acquire acquire;
				if (PyErr_CheckSignals() != 0)
					throw py::error_already_set();
			});
		}, py::arg("id"), py::arg("wait_time_in_ms") = INFINITE_WAIT_TIME, py::call_guard<py::gil_scoped_release>())
		.def("get_next_frame", [](DataStream &s, long wait_time_in_ms)
		{
			return s.GetNextFrame(wait_time_in_ms, []()
			{
				py::gil_scoped_acquire acquire;
				if (PyErr_CheckSignals() != 0)
					throw py::error_already_set();
			});
		}, py::arg("wait_time_in_ms") = INFINITE_WAIT_TIME, py::call_guard<py::gil_scoped_release>())
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
		.def("get", [](DataStream &s)
		{
			DataFrame frame = s.GetLatestFrame();
			return GetDataFromDataFrame(frame);
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
		.def_property_readonly("stream_id", &DataStream::GetStreamId)
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

	py::enum_<Severity>(m, "Severity")
		.value("CRITICAL", S_CRITICAL)
		.value("ERROR", S_ERROR)
		.value("WARNING", S_WARNING)
		.value("INFO", S_INFO)
		.value("DEBUG", S_DEBUG);

	m.def("submit_log_entry", &SubmitLogEntry);
	m.def("severity_to_string", &ConvertSeverityToString);

	py::class_<LogConsole>(m, "LogConsole")
		.def(py::init<bool, bool>(),
			py::arg("use_color") = true,
			py::arg("print_context") = true);

	py::class_<LogPublish>(m, "LogPublish")
		.def(py::init<std::string, std::string>());

#ifdef VERSION_INFO
	m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
	m.attr("__version__") = "dev";
#endif
}
