#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11_json/pybind11_json.hpp>

#include "DataStream.h"
#include "Timing.h"
#include "Service.h"
#include "Command.h"
#include "Property.h"
#include "Log.h"
#include "LogConsole.h"
#include "LogForwarder.h"
#include "Types.h"
#include "TestbedProxy.h"
#include "ServiceProxy.h"
#include "Server.h"
#include "Client.h"

#include "proto/testbed.pb.h"

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
};

py::dtype GetNumpyDataType(DataType type)
{
	switch (type)
	{
		case DataType::DT_UINT8:
			return py::dtype("uint8");
		case DataType::DT_UINT16:
			return py::dtype("uint16");
		case DataType::DT_UINT32:
			return py::dtype("uint32");
		case DataType::DT_UINT64:
			return py::dtype("uint64");
		case DataType::DT_INT8:
			return py::dtype("int8");
		case DataType::DT_INT16:
			return py::dtype("int16");
		case DataType::DT_INT32:
			return py::dtype("int32");
		case DataType::DT_INT64:
			return py::dtype("int64");
		case DataType::DT_FLOAT32:
			return py::dtype("float32");
		case DataType::DT_FLOAT64:
			return py::dtype("float64");
		case DataType::DT_COMPLEX64:
			return py::dtype("complex64");
		case DataType::DT_COMPLEX128:
			return py::dtype("complex128");
		default:
			throw pybind11::type_error("Data type is unknown.");
	}
}

py::object ToPython(const Value &value);

py::object ToPython(const List &list)
{
	py::list py_list;

	for (auto &item : list)
		py_list.append(ToPython(item));

	return py_list;
}

py::object ToPython(const Dict &dict)
{
	py::dict py_dict;

	for (auto const& [key, val] : dict)
		py_dict[py::cast(key)] = ToPython(val);

	return py_dict;
}

py::array ToPython(const Tensor &tensor, bool transfer_ownership = true)
{
	const Tensor *res;

	// TODO: This actually still makes a copy. Likely every ToPython() function
	// should be rewritten to use rvalues.
	if (transfer_ownership)
		res = new Tensor(std::move(tensor));
	else
		res = &tensor;

	size_t item_size = GetSizeOfDataType(res->m_DataType);

	std::vector<py::ssize_t> shape;
	for (size_t i = 0; i < res->m_NumDimensions; ++i)
	{
		shape.push_back(res->m_Dimensions[i]);
	}

	auto strides = py::detail::c_strides(shape, item_size);

	py::object capsule = py::none();

	if (transfer_ownership)
	{
		// Make sure the Tensor gets deleted after Python is done with it.
		capsule = py::capsule(res, [](void *ptr) {
			delete reinterpret_cast<Tensor *>(ptr);
		});
	}

	return py::array(
		GetNumpyDataType(res->m_DataType),
		shape,
		strides,
		res->m_Data,
		capsule
	);
}

py::object ToPython(const Value &value)
{
	if (std::holds_alternative<NoneValue>(value))
	{
		return py::none();
	}
	else if (std::holds_alternative<std::int64_t>(value))
	{
		return py::int_(std::get<std::int64_t>(value));
	}
	else if (std::holds_alternative<double>(value))
	{
		return py::float_(std::get<double>(value));
	}
	else if (std::holds_alternative<std::string>(value))
	{
		return py::str(std::get<std::string>(value));
	}
	else if (std::holds_alternative<bool>(value))
	{
		return py::bool_(std::get<bool>(value));
	}
	else if (std::holds_alternative<Dict>(value))
	{
		return ToPython(std::get<Dict>(value));
	}
	else if (std::holds_alternative<List>(value))
	{
		return ToPython(std::get<List>(value));
	}
	else if (std::holds_alternative<Tensor>(value))
	{
		return ToPython(std::get<Tensor>(value));
	}
	else
	{
		throw std::runtime_error("Unknown value type.");
	}
}

Value ValueFromPython(const py::handle &python_value)
{
	if (py::isinstance<py::none>(python_value))
	{
		return NoneValue();
	}
	else if (py::isinstance<py::buffer>(python_value))
	{
		auto buffer = python_value.cast<py::buffer>();
		auto buffer_info = buffer.request();

		auto dtype = GetDataTypeFromString(buffer_info.format);
		size_t ndim = buffer_info.ndim;
		void *data = buffer_info.ptr;

		if (ndim > 4)
			throw std::runtime_error("Input array must have at most four dimensions.");

		size_t shape[4];
		for (size_t i = 0; i < 4; ++i)
		{
			if (i < ndim)
			{
				shape[i] = buffer_info.shape[i];
			}
			else
			{
				shape[i] = 1;
			}
		}

		// Check if data is C continguous.
		auto strides = py::detail::c_strides(buffer_info.shape, GetSizeOfDataType(dtype));

		for (size_t i = 0; i < ndim; i++)
		{
			if (strides[i] != buffer_info.strides[i])
				throw std::runtime_error("Input array must be C continguous.");
		}

		Tensor tensor;
		tensor.Set(dtype, ndim, shape, (const char *) data);

		return tensor;
	}
	else if (py::isinstance<py::int_>(python_value))
	{
		return python_value.cast<std::int64_t>();
	}
	else if (py::isinstance<py::float_>(python_value))
	{
		return python_value.cast<double>();
	}
	else if (py::isinstance<py::str>(python_value))
	{
		return python_value.cast<std::string>();
	}
	else if (py::isinstance<py::bool_>(python_value))
	{
		return python_value.cast<bool>();
	}
	else if (py::isinstance<py::list>(python_value))
	{
		List list;

		for (const py::handle &item : python_value.cast<py::list>())
			list.push_back(ValueFromPython(item));

		return list;
	}
	else if (py::isinstance<py::dict>(python_value))
	{
		Dict dict;

		for (const auto &item : python_value.cast<py::dict>())
		{
			auto key = item.first.cast<std::string>();
			dict[key] = ValueFromPython(item.second);
		}

		return dict;
	}

	return NoneValue();
}

// A callback for long-running C++ functions. This function gets called
// periodically during the function call to allow Python KeyboardInterrupt
// to cancel the operation.
void error_check_python()
{
	py::gil_scoped_acquire acquire;

	if (PyErr_CheckSignals() != 0)
		throw py::error_already_set();
}

typedef std::function<std::string(py::bytes)> PythonRequestHandler;

PYBIND11_MODULE(catkit_bindings, m)
{
	py::class_<Server>(m, "Server")
		.def(py::init<int>())
		.def("register_request_handler", [](Server &server, std::string type, PythonRequestHandler request_handler)
		{
			server.RegisterRequestHandler(type, [request_handler](const std::string &data)
			{
				// Acquire the GIL before calling the request handler.
				py::gil_scoped_acquire acquire;
				return request_handler(py::bytes(data));
			});
		})
		.def("start", &Server::Start)
		.def("stop", &Server::Stop, py::call_guard<py::gil_scoped_release>())
		.def_property_readonly("is_running", &Server::IsRunning)
		.def_property_readonly("port", &Server::GetPort)
		.def("sleep", [](Server &server, double sleep_time_in_sec)
		{
			server.Sleep(sleep_time_in_sec, error_check_python);
		}, py::call_guard<py::gil_scoped_release>());

	py::class_<Client>(m, "Client")
		.def(py::init<std::string, int>())
		.def_property_readonly("host", &Client::GetHost)
		.def_property_readonly("port", &Client::GetPort)
		.def("make_request", &Client::MakeRequest, py::call_guard<py::gil_scoped_release>());

	py::class_<Service, TrampolineService>(m, "Service")
		.def(py::init<std::string, std::string, int, int>(),
			py::arg("service_type"),
			py::arg("service_id"),
			py::arg("service_port"),
			py::arg("testbed_port"))
		.def_property_readonly("id", &Service::GetId)
		.def_property_readonly("config", &Service::GetConfig)
		.def("run", [](Service &service)
		{
			service.Run(error_check_python);
		}, py::call_guard<py::gil_scoped_release>())
		.def("open", &Service::Open)
		.def("main", &Service::Main)
		.def("close", &Service::Close)
		.def("shut_down", &Service::ShutDown)
		.def_property_readonly("should_shut_down", &Service::ShouldShutDown)
		.def_property_readonly("testbed", &Service::GetTestbed)
		.def("sleep", [](Service &service, double sleep_time_in_sec)
		{
			service.Sleep(sleep_time_in_sec, error_check_python);
		}, py::call_guard<py::gil_scoped_release>())
		.def("make_property", [](Service &service, std::string name, py::object getter, py::object setter)
		{
			service.MakeProperty(name,
			[getter]()
			{
				py::gil_scoped_acquire acquire;

				return ValueFromPython(getter());
			},
			[setter](const Value &value)
			{
				py::gil_scoped_acquire acquire;

				setter(ToPython(value));
			});
		}, py::arg("name"), py::arg("getter") = nullptr, py::arg("setter") = nullptr)
		.def("make_command", [](Service &service, std::string name, py::object command)
		{
			service.MakeCommand(name, [command](const Dict &arguments)
			{
				py::gil_scoped_acquire acquire;

				py::dict kwargs = py::cast<py::dict>(ToPython(arguments));

				return ValueFromPython(command(**kwargs));
			});
		})
		.def("make_data_stream", [](Service &service, std::string stream_name, std::string type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
		{
			DataType dtype = GetDataTypeFromString(type);
			return service.MakeDataStream(stream_name, dtype, dimensions, num_frames_in_buffer);
		})
		.def("reuse_data_stream", &Service::ReuseDataStream);

	py::enum_<ServiceState>(m, "ServiceState")
		.value("CLOSED", ServiceState::CLOSED)
		.value("INITIALIZING", ServiceState::INITIALIZING)
		.value("OPENING", ServiceState::OPENING)
		.value("RUNNING", ServiceState::RUNNING)
		.value("CLOSING", ServiceState::CLOSING)
		.value("UNRESPONSIVE", ServiceState::UNRESPONSIVE)
		.value("CRASHED", ServiceState::CRASHED);

	m.def("is_alive_state", &IsAliveState);

	py::class_<ServiceProxy, std::shared_ptr<ServiceProxy>>(m, "ServiceProxy")
		.def(py::init<std::shared_ptr<TestbedProxy>, std::string>())
		.def("get_property", [](ServiceProxy &service, std::string name)
		{
			return ToPython(service.GetProperty(name, error_check_python));
		})
		.def("set_property", [](ServiceProxy &service, std::string name, py::handle obj)
		{
			auto val = service.SetProperty(name, ValueFromPython(obj), error_check_python);
			return ToPython(val);
		})
		.def("execute_command", [](ServiceProxy &service, std::string name, py::dict args)
		{
			auto res = service.ExecuteCommand(name, std::get<Dict>(ValueFromPython(args)), error_check_python);
			return ToPython(res);
		})
		.def("get_data_stream", [](ServiceProxy &service, std::string name)
		{
			return service.GetDataStream(name, error_check_python);
		})
		.def_property_readonly("state", &ServiceProxy::GetState)
		.def_property_readonly("is_alive", &ServiceProxy::IsAlive)
		.def_property_readonly("is_running", &ServiceProxy::IsRunning)
		.def_property_readonly("heartbeat", &ServiceProxy::GetHeartbeat)
		.def("start", [](ServiceProxy &service, double timeout_in_sec)
		{
			service.Start(timeout_in_sec, error_check_python);
		}, py::arg("timeout_in_sec") = -1.0)
		.def("stop", &ServiceProxy::Stop)
		.def("interrupt", &ServiceProxy::Interrupt)
		.def("terminate", &ServiceProxy::Terminate)
		.def_property_readonly("property_names", [](ServiceProxy &service)
		{
			return service.GetPropertyNames(error_check_python);
		})
		.def_property_readonly("command_names", [](ServiceProxy &service)
		{
			return service.GetCommandNames(error_check_python);
		})
		.def_property_readonly("data_stream_names", [](ServiceProxy &service)
		{
			return service.GetDataStreamNames(error_check_python);
		})
		.def_property_readonly("config", &ServiceProxy::GetConfig)
		.def_property_readonly("id", &ServiceProxy::GetId)
		.def_property_readonly("testbed", &ServiceProxy::GetTestbed);

	py::class_<TestbedProxy, std::shared_ptr<TestbedProxy>>(m, "TestbedProxy")
		.def(py::init<std::string, int>())
		.def("get_service", &TestbedProxy::GetService)
		.def("start_service", &TestbedProxy::StartService)
		.def("start_services", &TestbedProxy::StartServices)
		.def("interrupt_service", &TestbedProxy::InterruptService)
		.def("terminate_service", &TestbedProxy::TerminateService)
		.def("shut_down", &TestbedProxy::ShutDown)
		.def_property_readonly("is_simulated", &TestbedProxy::IsSimulated)
		.def_property_readonly("is_alive", &TestbedProxy::IsAlive)
		.def_property_readonly("heartbeat", &TestbedProxy::GetHeartbeat)
		.def_property_readonly("config", &TestbedProxy::GetConfig)
		.def_property_readonly("host", &TestbedProxy::GetHost)
		.def_property_readonly("logging_egress_port", &TestbedProxy::GetLoggingEgressPort)
		.def_property_readonly("active_services", &TestbedProxy::GetActiveServices)
		.def_property_readonly("inactive_services", &TestbedProxy::GetInactiveServices)
		.def_property_readonly("logging_ingress_port", &TestbedProxy::GetLoggingIngressPort)
		.def_property_readonly("logging_egress_port", &TestbedProxy::GetLoggingEgressPort)
		.def_property_readonly("data_logging_ingress_port", &TestbedProxy::GetDataLoggingIngressPort)
		.def_property_readonly("data_logging_egress_port", &TestbedProxy::GetDataLoggingEgressPort)
		.def_property_readonly("tracing_ingress_port", &TestbedProxy::GetTracingIngressPort)
		.def_property_readonly("tracing_egress_port", &TestbedProxy::GetTracingEgressPort);

	py::class_<DataFrame>(m, "DataFrame")
		.def_property_readonly("id", [](const DataFrame &f)
			{
				return f.m_Id;
			})
		.def_property_readonly("timestamp", [](const DataFrame &f)
			{
				return f.m_TimeStamp;
			})
		.def_property_readonly("data", [](DataFrame &frame)
		{
			Tensor &tensor = frame;
			return ToPython(tensor, false);
		});

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
		.def("copy", [](DataStream &s)
		{
			return DataStream::Open(s.GetStreamId());
		})
		.def("request_new_frame", &DataStream::RequestNewFrame)
		.def("submit_frame", &DataStream::SubmitFrame)
		.def("submit_data", [](DataStream &s, py::buffer data)
		{
			auto buffer_info = data.request();

			// Check if data has the right dtype.
			auto input_dtype = GetDataTypeFromString(buffer_info.format);
			if (s.GetDataType() != input_dtype)
				throw std::runtime_error(std::string("Incompatible array dtype. Stream: ") + GetDataTypeAsString(s.GetDataType()) + ". Input: " + GetDataTypeAsString(input_dtype));

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
			return s.GetFrame(id, wait_time_in_ms, error_check_python);
		}, py::arg("id"), py::arg("wait_time_in_ms") = INFINITE_WAIT_TIME, py::call_guard<py::gil_scoped_release>())
		.def("get_next_frame", [](DataStream &s, long wait_time_in_ms)
		{
			return s.GetNextFrame(wait_time_in_ms, error_check_python);
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
			return ToPython(frame, false);
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
		.def_property_readonly("owner_pid", &DataStream::GetOwnerPID)
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

	py::class_<LogForwarder>(m, "LogForwarder")
		.def(py::init<std::string, std::string>());

#ifdef VERSION_INFO
	m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
	m.attr("__version__") = "dev";
#endif
}
