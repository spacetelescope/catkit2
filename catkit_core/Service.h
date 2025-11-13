#ifndef SERVICE_H
#define SERVICE_H

#include <vector>
#include <string>
#include <map>
#include <vector>
#include <memory>
#include <thread>
#include <tuple>
#include <functional>

#include <zmq.hpp>
#include <nlohmann/json.hpp>

#include "Command.h"
#include "DataStream.h"
#include "LogConsole.h"
#include "LogForwarder.h"
#include "Server.h"
#include "ServiceState.h"
#include "ProcessStats.h"
#include "Types.h"

const double SERVICE_LIVELINESS = 5;

class TestbedProxy;

typedef std::function<Value()> PropertyGetter;
typedef std::function<void(const Value &)> PropertySetter;

class Service
{
public:

	Service(std::string service_type, std::string service_id, int service_port, int testbed_port);
	virtual ~Service();

	void Run(void (*error_check)()=nullptr);

	virtual void Open();
	virtual void Main();
	virtual void Close();

	void ShutDown();
	bool ShouldShutDown();
	bool IsRunning();

	void Sleep(double sleep_time_in_sec, void (*error_check)()=nullptr);

	std::shared_ptr<Command> GetCommand(const std::string &command_name) const;
	std::shared_ptr<DataStream> GetDataStream(const std::string &stream_name) const;

	nlohmann::json GetConfig() const;
	const std::string &GetId() const;

	void MakeProperty(std::string property_name, PropertyGetter getter, PropertySetter setter = nullptr);
	void MakeCommand(std::string command_name, Command::CommandFunction func);
	std::shared_ptr<DataStream> MakeDataStream(std::string stream_name, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer);
	std::shared_ptr<DataStream> ReuseDataStream(std::string stream_name, std::string stream_id);

	std::shared_ptr<TestbedProxy> GetTestbed();

	void CleanupAttributes();

private:
	std::string GetProperty(std::string property_name);
	void SetProperty(std::string property_name, std::string_view value);

	std::string HandleGetInfo(const std::string &data);

	std::string HandleExecuteCommand(const std::string &data);

	std::string HandleShutDown(const std::string &data);

	void MonitorSafety();
	bool IsSafe();
	bool RequiresSafety();

	void MonitorHeartbeats();
	void MonitorProperties();

	void UpdateState(ServiceState state);

	Server m_Server;

	std::atomic_bool m_IsRunning;
	std::atomic_bool m_ShouldShutDown;
	std::atomic_bool m_FailSafe;
	std::atomic_bool m_IsBeingDestroyed;

	std::shared_ptr<TestbedProxy> m_Testbed;

	std::string m_ServiceId;
	std::string m_ServiceType;

	nlohmann::json m_Config;

	std::shared_ptr<DataStream> m_Heartbeat;
	std::shared_ptr<DataStream> m_Safety;
	std::shared_ptr<DataStream> m_State;

	std::map<std::string, std::pair<PropertyGetter, PropertySetter>> m_Properties;

	std::map<std::string, std::shared_ptr<Command>> m_Commands;
	std::map<std::string, std::shared_ptr<DataStream>> m_DataStreams;

	LogConsole m_LoggerConsole;
	LogForwarder m_LoggerPublish;

	ProcessStats m_ProcessStats;
};

std::tuple<std::string, int, int> ParseServiceArgs(std::vector<std::string> arguments);

#endif // SERVICE_H
