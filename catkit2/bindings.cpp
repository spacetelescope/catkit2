#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11_json/pybind11_json.hpp>
#include <cctype>
#include <string>
#include <vector>
#include <variant>
#include <charconv>

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
#include "HostName.h"
#include "Tracing.h"
#include "MessageBroker.h"
#include "LocalMemory.h"
#include "SharedMemory.h"
#include "Shareable.h"
#include "Memory.h"
#include "Event.h"
#include "BuddyAllocator.h"
#include "PoolAllocator.h"
#include "HybridPoolAllocator.h"
#include "Event.h"
#include "Uuid.h"

#include "testbed.pb.h"

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

ArrayInfo FormatStringToDtype(std::string_view format)
{
	if (format.size() == 0)
		throw std::runtime_error("The format was incorrectly formatted.");

	ArrayInfo array_info;

	// Deduce the endian with a default.
	array_info.byte_order = '=';

	if (format[0] == '<' || format[0] == '>' || format[0] == '!' || format[0] == '=')
	{
		array_info.byte_order = format[0];
		format = format.substr(1);
	}

	if (format.size() == 0)
		throw std::runtime_error("The format was incorrectly formatted.");

	// Deduce the data type from the character codes.
	if (format[0] == 'b' ||
		format[0] == 'h' ||
		format[0] == 'i' ||
		format[0] == 'l' ||
		format[0] == 'q'
	)
	{
		array_info.data_type = 'i';
	}
	else if (
		format[0] == 'B' ||
		format[0] == 'H' ||
		format[0] == 'I' ||
		format[0] == 'L' ||
		format[0] == 'Q'
	)
	{
		array_info.data_type = 'u';
	}
	else if (
		format[0] == 'f' ||
		format[0] == 'd' ||
		format[0] == 'g' ||
		format[0] == 'e'
	)
	{
		array_info.data_type = 'f';
	}
	else if (format[0] == 'Z')
	{
		if (format.size() < 2)
			throw std::runtime_error("The format was incorrection formatted.");

		if (format[1] == 'f' || format[1] == 'd')
		{
			array_info.data_type = 'c';
		}
		else
		{
			throw std::runtime_error("The format was incorrectly formatted.");
		}
	}
	else
	{
		throw std::runtime_error("The format was incorrectly formatted.");
	}

	return array_info;
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

py::dtype DtypeToPython(const ArrayInfo *array_info)
{
	char dtype_buf[6];
	dtype_buf[0] = array_info->byte_order;
	dtype_buf[1] = array_info->data_type;

	auto [ptr, ec] = std::to_chars(dtype_buf + 2, dtype_buf + sizeof(dtype_buf) - 1, array_info->item_size);
	if (ec != std::errc())
	{
		auto error_message = std::make_error_code(ec).message();
		throw std::runtime_error("Failed to convert item size to string: " + error_message);
	}
	*ptr = '\0';

	return py::dtype(dtype_buf);
}

py::array ToPython(void *payload, const ArrayInfo *array_info)
{
	auto dtype = DtypeToPython(array_info);

	std::vector<py::ssize_t> shape(array_info->ndim);
	std::vector<py::ssize_t> strides(array_info->ndim);

	for (size_t i = 0; i < array_info->ndim; ++i)
	{
		shape[i] = array_info->shape[i];
		strides[i] = array_info->strides[i];
	}

	return py::array(
		dtype,
		shape,
		strides,
		payload
	);
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

DataType GetDataTypeFromBufferInfo(py::buffer_info &buffer_info)
{
	if (buffer_info.format == "B" || buffer_info.format == "b" ||
		buffer_info.format == "H" || buffer_info.format == "h" ||
		buffer_info.format == "I" || buffer_info.format == "i" ||
		buffer_info.format == "Q" || buffer_info.format == "q" ||
		buffer_info.format == "L" || buffer_info.format == "l")
	{
		// Get the exact data type from the number of bytes per integer.
		// Integer size is platform dependent.
		switch (buffer_info.itemsize)
		{
			case 1:
				return std::isupper(buffer_info.format[0]) ? DataType::DT_UINT8 : DataType::DT_INT8;
			case 2:
				return std::isupper(buffer_info.format[0]) ? DataType::DT_UINT16 : DataType::DT_INT16;
			case 4:
				return std::isupper(buffer_info.format[0]) ? DataType::DT_UINT32 : DataType::DT_INT32;
			case 8:
				return std::isupper(buffer_info.format[0]) ? DataType::DT_UINT64 : DataType::DT_INT64;
			default:
				throw std::runtime_error("No integer datatype with this size.");
		}
	}
	else if (buffer_info.format == "f")
	{
		return DataType::DT_FLOAT32;
	}
	else if (buffer_info.format == "d")
	{
		return DataType::DT_FLOAT64;
	}
	else if (buffer_info.format == "F" || buffer_info.format == "Zf")
	{
		return DataType::DT_COMPLEX64;
	}
	else if (buffer_info.format == "D" || buffer_info.format == "Zd")
	{
		return DataType::DT_COMPLEX128;
	}
	else
	{
		throw std::runtime_error("Buffer format " + buffer_info.format + " not recognized.");
	}
}

class MetadataWrapper
{
public:
	MetadataWrapper(Message *message)
		: m_Message(message)
	{
	}

	py::object GetItem(std::string key) const
	{
		auto entry = m_Message->GetMetadataEntry(key);

		if (entry == nullptr)
		{
			throw pybind11::key_error(key);
		}

		switch (entry->type)
		{
		case MetadataType::Integer:
			return py::int_(entry->value.integer);
		case MetadataType::Float:
			return py::float_(entry->value.floating_point);
		case MetadataType::String:
			return py::str(entry->value.string.data());
		default:
			throw std::runtime_error("Unknown metadata type.");
		}
	}

	void SetItem(std::string key, const py::object &obj)
	{
		if (py::isinstance<py::int_>(obj))
		{
			m_Message->SetMetadataEntry(key, py::cast<std::int64_t>(obj));
		}
		else if (py::isinstance<py::float_>(obj))
		{
			m_Message->SetMetadataEntry(key, py::cast<double>(obj));
		}
		else if (py::isinstance<py::str>(obj))
		{
			m_Message->SetMetadataEntry(key, py::cast<std::string>(obj));
		}
		else
		{
			throw std::runtime_error("Metadata entry value must be an integer, float or string.");
		}
	}

private:
	Message *m_Message;
	size_t m_NumEntries;
};

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
		.def("make_request", [](Client &client, const std::string &what, py::bytes request)
		{
			// Make sure that we are only accepting and converting bytes, not string.
			std::string request_string = request;
			std::string res;

			{
				py::gil_scoped_release release;
				res = client.MakeRequest(what, request_string);
			}

			return py::bytes(res);
		});

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
		.def("make_property", [](Service &service, std::string name, py::object getter, py::object setter, std::string type)
		{
			DataType dtype = GetDataTypeFromString(type);
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
			},
			dtype);
		}, py::arg("name"), py::arg("getter") = nullptr, py::arg("setter") = nullptr, py::arg("type") = "")
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
		.value("CRASHED", ServiceState::CRASHED)
		.value("FAIL_SAFE", ServiceState::FAIL_SAFE);

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
		.def("stop_service", &TestbedProxy::StopService)
		.def("interrupt_service", &TestbedProxy::InterruptService)
		.def("terminate_service", &TestbedProxy::TerminateService)
		.def("shut_down", &TestbedProxy::ShutDown)
		.def_property_readonly("is_simulated", &TestbedProxy::IsSimulated)
		.def_property_readonly("is_alive", &TestbedProxy::IsAlive)
		.def_property_readonly("heartbeat", &TestbedProxy::GetHeartbeat)
		.def_property_readonly("config", &TestbedProxy::GetConfig)
		.def_property_readonly("host", &TestbedProxy::GetHost)
		.def_property_readonly("port", &TestbedProxy::GetPort)
		.def_property_readonly("logging_egress_port", &TestbedProxy::GetLoggingEgressPort)
		.def_property_readonly("active_services", &TestbedProxy::GetActiveServices)
		.def_property_readonly("inactive_services", &TestbedProxy::GetInactiveServices)
		.def_property_readonly("logging_ingress_port", &TestbedProxy::GetLoggingIngressPort)
		.def_property_readonly("logging_egress_port", &TestbedProxy::GetLoggingEgressPort)
		.def_property_readonly("data_logging_ingress_port", &TestbedProxy::GetDataLoggingIngressPort)
		.def_property_readonly("data_logging_egress_port", &TestbedProxy::GetDataLoggingEgressPort)
		.def_property_readonly("tracing_ingress_port", &TestbedProxy::GetTracingIngressPort)
		.def_property_readonly("tracing_egress_port", &TestbedProxy::GetTracingEgressPort)
		.def_property_readonly("base_data_path", &TestbedProxy::GetBaseDataPath)
		.def_property_readonly("support_data_path", &TestbedProxy::GetSupportDataPath)
		.def_property_readonly("long_term_monitoring_path", &TestbedProxy::GetLongTermMonitoringPath)
		.def_property_readonly("mode", &TestbedProxy::GetMode);

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
		.def_static("create", [](std::string &stream_name, std::string &service_id, std::string &type, std::vector<size_t> dimensions, size_t num_frames_in_buffer)
		{
			DataType dtype = GetDataTypeFromString(type);
			auto stream = DataStream::Create(stream_name, service_id, dtype, dimensions, num_frames_in_buffer);

			return std::shared_ptr<DataStream>(std::move(stream));
		})
		.def_static("open", [](std::string &stream_id)
		{
			auto stream = DataStream::Open(stream_id);
			return std::shared_ptr<DataStream>(std::move(stream));
		})
		.def("copy", [](DataStream &s)
		{
			auto stream = DataStream::Open(s.GetStreamId());
			return std::shared_ptr<DataStream>(std::move(stream));
		})
		.def("request_new_frame", &DataStream::RequestNewFrame)
		.def("submit_frame", &DataStream::SubmitFrame)
		.def("submit_data", [](DataStream &s, py::buffer data)
		{
			auto buffer_info = data.request();

			// Check if data has the right dtype.
			auto input_dtype = GetDataTypeFromBufferInfo(buffer_info);
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
			return GetNumpyDataType(s.GetDataType());
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
		.def_property_readonly("frame_rate", &DataStream::GetFrameRate)
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
	m.def("get_host_name", &GetHostName);
	m.def("parse_service_args", [](std::vector<std::string> arguments)
	{
		return ParseServiceArgs(arguments);
	});

	py::class_<LogConsole>(m, "LogConsole")
		.def(py::init<bool, bool>(),
			py::arg("use_color") = true,
			py::arg("print_context") = true);

	py::class_<LogForwarder>(m, "LogForwarder")
		.def(py::init<>())
		.def("connect", &LogForwarder::Connect);

	m.def("trace_connect", [](std::string process_name, std::string host, int port) {
		tracing_proxy.Connect(process_name, host, port);
	});
	m.def("trace_disconnect", []() {
		tracing_proxy.Disconnect();
	});
	m.def("trace_interval", [](std::string name, std::string category, uint64_t timestamp_start, uint64_t duration) {
		tracing_proxy.TraceInterval(name, category, timestamp_start, duration);
	});
	m.def("trace_instant", [](std::string name, uint64_t timestamp) {
		tracing_proxy.TraceInstant(name, timestamp);
	});
	m.def("trace_counter", [](std::string name, std::string series, uint64_t timestamp, double counter) {
		tracing_proxy.TraceCounter(name, series, timestamp, counter);
	});

	py::enum_<MetadataType>(m, "MetadataType")
		.value("Integer", MetadataType::Integer)
		.value("Float", MetadataType::Float)
		.value("String", MetadataType::String);

	py::class_<Shareable, std::shared_ptr<Shareable>>(m, "Shareable");

	py::class_<Memory, std::shared_ptr<Memory>>(m, "Memory");

	py::class_<SharedMemory, Memory, std::shared_ptr<SharedMemory>>(m, "SharedMemory")
		.def_static("create", [](std::string name, size_t size)
		{
			auto mem = SharedMemory::Create(name, size);

			return std::shared_ptr<SharedMemory>(std::move(mem));
		})
		.def_static("open", [](std::string name)
		{
			auto mem = SharedMemory::Open(name);
			return std::shared_ptr<SharedMemory>(std::move(mem));
		})
		.def("get_memory", [](std::shared_ptr<SharedMemory> memory)
		{
			auto address = memory->GetAddress();
			size_t capacity = memory->GetCapacity();

			return py::memoryview::from_memory(address, capacity);
		});

	py::class_<LocalMemory, Memory, std::shared_ptr<LocalMemory>>(m, "LocalMemory")
		.def_static("create", [](size_t num_bytes)
		{
			auto mem = LocalMemory::Create(num_bytes);
			return std::shared_ptr<LocalMemory>(std::move(mem));
		})
		.def("get_memory", [](std::shared_ptr<LocalMemory> memory)
		{
			auto address = memory->GetAddress();
			size_t capacity = memory->GetCapacity();

			return py::memoryview::from_memory(address, capacity);
		});

	py::class_<Uuid>(m, "Uuid")
		.def_static("generate", []()
		{
			Uuid uuid;
			uuid.Generate(&uuid);
			return uuid;
		})
		.def("__str__", &Uuid::to_string)
		.def("__repr__", &Uuid::to_string);

	py::class_<MetadataWrapper>(m, "Metadata")
		.def("__getitem__", &MetadataWrapper::GetItem)
		.def("__setitem__", &MetadataWrapper::SetItem);

	py::class_<ArrayInfo>(m, "ArrayInfo")
		.def(py::init<>())
		.def_property("dtype", [](ArrayInfo &info)
		{
			return DtypeToPython(&info);
		}, [](ArrayInfo &info, py::dtype dtype)
		{
			info.data_type = dtype.kind();
			info.item_size = dtype.itemsize();
			info.byte_order = dtype.byteorder();
		})
		.def_property("item_size", [](ArrayInfo &info) { return info.item_size; }, [](ArrayInfo &info, uint8_t value) { info.item_size = value; })
		.def_property("ndim", [](ArrayInfo &info) { return info.ndim; }, [](ArrayInfo &info, uint8_t value) { info.ndim = value; })
		.def_property("shape", [](const ArrayInfo& ai) {
			return std::vector<uint32_t>(ai.shape, ai.shape + ai.ndim);
		}, [](ArrayInfo &info, const py::list &value)
		{
			info.ndim = static_cast<uint8_t>(value.size());
			for (size_t i = 0; i < value.size(); ++i)
			{
				info.shape[i] = static_cast<uint32_t>(py::cast<int64_t>(value[i]));
			}
		})
		.def_property("strides", [](const ArrayInfo& ai)
		{
			return std::vector<uint32_t>(ai.strides, ai.strides + ai.ndim);
		}, [](ArrayInfo &info, const py::list &value)
		{
			info.ndim = static_cast<uint8_t>(value.size());
			for (size_t i = 0; i < value.size(); ++i)
			{
				info.strides[i] = static_cast<uint32_t>(py::cast<int64_t>(value[i]));
			}
		})
		.def_property_readonly("num_items", &ArrayInfo::GetNumItems)
		.def_property_readonly("num_bytes", &ArrayInfo::GetNumBytes);

	py::class_<Message>(m, "Message")
		.def_property_readonly("topic", &Message::GetTopic)
		.def_property_readonly("trace_id", &Message::GetTraceId)
		.def_property_readonly("payload_id", &Message::GetPayloadId)
		.def_property_readonly("producer_hostname", &Message::GetProducerHostname)
		.def_property_readonly("producer_pid", &Message::GetProducerPid)
		.def_property_readonly("producer_timestamp", &Message::GetProducerTimestamp)
		.def_property("array_info", &Message::GetArrayInfo, &Message::SetArrayInfo)
		.def_property("payload", [](const Message& m) {
			return ToPython(m.GetPayload(), &m.GetArrayInfo());
		},
		[](Message &m, py::buffer data)
		{
			py::buffer_info buffer_info = data.request();
			ArrayInfo array_info = FormatStringToDtype(buffer_info.format);

			array_info.item_size = buffer_info.itemsize;

			// Deduce the number of dimensions.
			array_info.ndim = buffer_info.ndim;
			if (array_info.ndim > MAX_NUM_DIMENSIONS)
				throw std::runtime_error("The array is too high-dimensional.");

			// Copy over the shape and strides.
			std::transform(buffer_info.shape.begin(), buffer_info.shape.end(), array_info.shape, [](const auto& val) { return static_cast<uint32_t>(val); });
			std::transform(buffer_info.strides.begin(), buffer_info.strides.end(), array_info.strides, [](const auto& val) { return static_cast<uint32_t>(val); });

			// Make sure our buffer is large enough.
			if (array_info.GetNumBytes() > m.GetPayloadSize())
				throw std::runtime_error("The buffer is too small.");

			// All checks are complete. Let's copy the raw data.
			std::memcpy(m.GetPayload(), buffer_info.ptr, array_info.GetNumBytes());
			m.SetArrayInfo(array_info);
		})
		.def_property_readonly("payload_size", &Message::GetPayloadSize)
		.def_property_readonly("metadata", [](Message *message)
		{
			return MetadataWrapper(message);
		})
		.def_property("start_byte", &Message::GetStartByte, &Message::SetStartByte)
		.def_property("end_byte", &Message::GetEndByte, &Message::SetEndByte);

	py::enum_<EventWaitMethod>(m, "EventWaitMethod")
		.value("Default", EventWaitMethod::Default)
		.value("ConditionVariable", EventWaitMethod::ConditionVariable)
		.value("Futex", EventWaitMethod::Futex)
		.value("Semaphore", EventWaitMethod::Semaphore)
		.value("SpinLock", EventWaitMethod::SpinLock);

	py::class_<Event, std::shared_ptr<Event>>(m, "Event")
		.def_static("create", [](std::shared_ptr<Memory> memory, std::string id)
		{
			auto stream = StructStream(memory->GetAddress());
			return Event::Create(stream, id);
		})
		.def_static("open", [](std::shared_ptr<Memory> memory)
		{
			auto stream = StructStream(memory->GetAddress());
			return Event::Open(stream);
		})
		.def("wait", [](std::shared_ptr<Event> event, py::object condition, double timeout_in_seconds, EventWaitMethod wait_method)
		{
			event->Wait(timeout_in_seconds, [condition]()
			{
				py::gil_scoped_acquire acquire;

				return py::cast<bool>(condition());
			}, wait_method, error_check_python);
		}, py::arg("condition"), py::arg("timeout_in_sec") = -1, py::arg("wait_method") = EventWaitMethod::Default, py::call_guard<py::gil_scoped_release>())
		.def("signal", &Event::Signal, py::call_guard<py::gil_scoped_release>())
		.def("__enter__", [](std::shared_ptr<Event> event)
		{
			event->Lock();
			return event;
		}, py::call_guard<py::gil_scoped_release>())
		.def("__exit__", [] (std::shared_ptr<Event> event, const std::optional<pybind11::type> &exc_type, const std::optional<pybind11::object> &exc_value, const std::optional<pybind11::object> &traceback)
		{
			event->Unlock();
		}, py::call_guard<py::gil_scoped_release>());

	py::enum_<MessageSubscriptionMode>(m, "MessageSubscriptionMode")
		.value("NewestOnly", MessageSubscriptionMode::NewestOnly)
		.value("Sequential", MessageSubscriptionMode::Sequential);

	py::class_<MessageSubscription>(m, "MessageSubscription")
		.def("get_next_message", [](MessageSubscription &subscription, double timeout_in_seconds = -1, EventWaitMethod wait_method = EventWaitMethod::Default)
		{
			return subscription.GetNextMessage(timeout_in_seconds, wait_method, error_check_python);
		}, py::arg("timeout_in_sec") = -1, py::arg("wait_method") = EventWaitMethod::Default, py::call_guard<py::gil_scoped_release>())
		.def("try_get_next_message", [](MessageSubscription &subscription) -> py::object
		{
			auto res = subscription.TryGetNextMessage();
			if (res)
				return py::cast(res.value());

			return py::none();
		})
		.def_property_readonly("next_message_id", &MessageSubscription::GetNextMessageId);

	py::class_<MessageBroker, std::shared_ptr<MessageBroker>>(m, "MessageBroker")
		.def_static("create", [](std::shared_ptr<Memory> header, std::vector<std::shared_ptr<Memory>> memory_blocks)
		{
			auto stream = StructStream(header->GetAddress());
			auto broker = MessageBroker::Create(stream, memory_blocks);

			return std::shared_ptr<MessageBroker>(std::move(broker));
		})
		.def_static("open", [](std::shared_ptr<Memory> memory)
		{
			auto stream = StructStream(memory->GetAddress());
			auto broker = MessageBroker::Open(stream);

			return std::shared_ptr<MessageBroker>(std::move(broker));
		})
		.def("prepare_message", [](std::shared_ptr<MessageBroker> broker, const std::string& topic, std::size_t payload_size, std::uint8_t memory_block_id)
		{
			auto message = broker->PrepareMessage(topic, payload_size, memory_block_id);

			return message;
		}, py::arg("topic"), py::arg("payload_size"), py::arg("memory_block_id") = 0)
		.def("prepare_message", [](std::shared_ptr<MessageBroker> broker, const std::string& topic, std::size_t payload_size, py::object trace_id, std::uint8_t memory_block_id)
		{
			if (trace_id.is_none())
			{
				return broker->PrepareMessage(topic, payload_size, memory_block_id);
			}
			else
			{
				return broker->PrepareMessage(topic, payload_size, py::cast<Uuid>(trace_id), memory_block_id);
			}
		}, py::arg("topic"), py::arg("payload_size"), py::arg("trace_id") = py::none(), py::arg("memory_block_id") = 0)
		.def("publish_message", [](std::shared_ptr<MessageBroker> broker, Message& message, bool is_final)
		{
			broker->PublishMessage(message, is_final);
		}, py::arg("message"), py::arg("is_final") = true)
		.def("publish_data", [](std::shared_ptr<MessageBroker> broker, std::string topic, py::bytes data, py::object trace_id, std::uint8_t memory_block_id)
		{
			if (trace_id.is_none())
			{
				broker->PublishData(topic, PyBytes_AsString(data.ptr()), PyBytes_Size(data.ptr()), memory_block_id);
			}
			else
			{
				broker->PublishData(topic, PyBytes_AsString(data.ptr()), PyBytes_Size(data.ptr()), py::cast<Uuid>(trace_id), memory_block_id);
			}
		}, py::arg("topic"), py::arg("data"), py::arg("trace_id") = py::none(), py::arg("memory_block_id") = 0)
		.def("try_get_message", [](std::shared_ptr<MessageBroker> broker, std::string_view topic, size_t frame_id) -> py::object
		{
			auto res = broker->TryGetMessage(topic, frame_id);
			if (res)
				return py::cast(res.value());

			return py::none();
		}, py::arg("topic"), py::arg("frame_id"))
		.def("get_newest_message", [](std::shared_ptr<MessageBroker> broker, std::string_view topic) -> py::object
		{
			auto res = broker->GetNewestMessage(topic);
			if (res)
				return py::cast(res.value());

			return py::none();
		}, py::arg("topic"))
		.def("is_message_available", &MessageBroker::IsMessageAvailable)
		.def("will_message_be_available", &MessageBroker::WillMessageBeAvailable)
		.def("get_newest_message_id", &MessageBroker::GetNewestMessageId)
		.def("get_oldest_message_id", &MessageBroker::GetOldestMessageId)
		.def("get_message_rate", &MessageBroker::GetMessageRate)
		.def("get_all_message_topics", &MessageBroker::GetAllMessageTopics)
		.def("subscribe", [](std::shared_ptr<MessageBroker> broker, std::string topic, py::object starting_frame_id, MessageSubscriptionMode mode)
		{
			// Check if the starting frame ID is a number or None.
			if (starting_frame_id.is_none())
			{
				return broker->Subscribe(topic, mode);
			}
			else
			{
				return broker->Subscribe(topic, py::cast<std::uint64_t>(starting_frame_id), mode);
			}
		}, py::arg("topic"), py::arg("starting_frame_id") = py::none(), py::arg("mode") = MessageSubscriptionMode::NewestOnly);

	py::class_<PoolAllocator, std::shared_ptr<PoolAllocator>>(m, "PoolAllocator")
		.def_static("create", [](std::shared_ptr<Memory> memory, std::uint32_t capacity)
		{
			auto stream = StructStream(memory->GetAddress());
			auto allocator = PoolAllocator::Create(stream, capacity);

			return std::shared_ptr<PoolAllocator>(std::move(allocator));
		})
		.def_static("open", [](std::shared_ptr<Memory> memory)
		{
			auto stream = StructStream(memory->GetAddress());
			auto allocator = PoolAllocator::Open(stream);

			return std::shared_ptr<PoolAllocator>(std::move(allocator));
		})
		.def("allocate", [](std::shared_ptr<PoolAllocator> allocator)
		{
			auto handle = allocator->Allocate();

			if (handle == PoolAllocator::INVALID_HANDLE)
				throw std::runtime_error("Failed to allocate memory from pool allocator.");

			return handle;
		})
		.def("release", &PoolAllocator::Release)
		.def("acquire", &PoolAllocator::Acquire);

	py::class_<BuddyAllocator, std::shared_ptr<BuddyAllocator>>(m, "BuddyAllocator")
		.def_static("create", [](std::shared_ptr<Memory> memory, std::size_t max_size, std::size_t min_size)
		{
			auto stream = StructStream(memory->GetAddress());
			auto allocator = BuddyAllocator::Create(stream, max_size, min_size);

			return std::shared_ptr<BuddyAllocator>(std::move(allocator));
		})
		.def_static("open", [](std::shared_ptr<Memory> memory)
		{
			auto stream = StructStream(memory->GetAddress());
			auto allocator = BuddyAllocator::Open(stream);

			return std::shared_ptr<BuddyAllocator>(std::move(allocator));
		})
		.def("allocate", [](std::shared_ptr<BuddyAllocator> allocator, std::size_t size)
		{
			auto handle = allocator->Allocate(size);

			if (handle == BuddyAllocator::INVALID_HANDLE)
				throw std::runtime_error("Failed to allocate memory from buddy allocator.");

			return handle;
		})
		.def("acquire", &BuddyAllocator::Acquire)
		.def("release", &BuddyAllocator::Release)
		.def("print_state", &BuddyAllocator::PrintState);

	py::class_<HybridPoolAllocator, std::shared_ptr<HybridPoolAllocator>>(m, "HybridPoolAllocator")
		.def_static("create", [](std::shared_ptr<Memory> memory, std::size_t max_size, std::size_t min_size, std::size_t min_size_pool)
		{
			auto stream = StructStream(memory->GetAddress());
			auto allocator = HybridPoolAllocator::Create(stream, max_size, min_size, min_size_pool);

			return std::shared_ptr<HybridPoolAllocator>(std::move(allocator));
		})
		.def_static("open", [](std::shared_ptr<Memory> memory)
		{
			auto stream = StructStream(memory->GetAddress());
			auto allocator = HybridPoolAllocator::Open(stream);

			return std::shared_ptr<HybridPoolAllocator>(std::move(allocator));
		})
		.def("allocate", [](std::shared_ptr<HybridPoolAllocator> allocator, std::size_t size)
		{
			auto handle = allocator->Allocate(size);

			if (handle == HybridPoolAllocator::INVALID_HANDLE)
				throw std::runtime_error("Failed to allocate memory from buddy allocator.");

			return handle;
		})
		.def("acquire", &HybridPoolAllocator::Acquire)
		.def("release", &HybridPoolAllocator::Release);

#ifdef VERSION_INFO
	m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
	m.attr("__version__") = "dev";
#endif
}
