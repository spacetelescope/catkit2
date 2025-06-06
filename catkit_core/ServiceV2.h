#ifndef SERVICE_V2_H
#define SERVICE_V2_H

#include <vector>
#include <string>
#include <map>
#include <thread>

#include <zmq.hpp>
#include <nlohmann/json.hpp>

#include "Property.h"
#include "Command.h"
#include "DataStream.h"
#include "LogConsole.h"
#include "LogForwarder.h"
#include "Server.h"
#include "ServiceState.h"

class TestbedProxy;

class ServiceV2
{
public:
	ServiceV2(std::string service_type, std::string service_id, );
	virtual ~ServiceV2();

	void Run(void (*error_check)()=nullptr);

	virtual void Open();
	virtual void Main();
	virtual void Close();

	void ShutDown();
	bool ShouldShutDown();
	bool IsRunning();

	void Sleep(double sleep_time_in_sec, void (*error_check)()=nullptr);

	nlohmann::json GetConfig() const;
	const std::string &GetId() const;

	void MakeProperty(std::string property_name, Property::Getter getter, Property::Setter setter = nullptr, DataType dtype = DataType::DT_UNKNOWN);
	void MakeCommand(std::string command_name, Command::CommandFunction func);
	std::shared_ptr<DataStream> MakeDataStream(std::string stream_name, DataType type, std::vector<size_t> dimensions, size_t num_frames_in_buffer);

	std::shared_ptr<TestbedProxy> GetTestbed();

	void CleanupAttributes();

private:
	void MonitorSafety();
	bool IsSafe();
	bool RequiresSafety();

	void UpdateState(ServiceState state);

	std::atomic_bool m_IsRunning;
	std::atomic_bool m_ShouldShutDown;
	std::atomic_bool m_FailSafe;

	std::shared_ptr<TestbedProxy> m_Testbed;

	std::string m_ServiceId;
	std::string m_ServiceType;

	nlohmann::json m_Config;

	LogConsole m_LoggerConsole;
	LogForwarder m_LoggerPublish;
};

std::tuple<std::string, int, int> ParseServiceArgs(std::vector<std::string> arguments);

#endif // SERVICE_V2_H
