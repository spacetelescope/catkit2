#ifndef SERVICE_PROXY_H
#define SERVICE_PROXY_H

#include "Types.h"
#include "DataStream.h"
#include "ServiceState.h"
#include "Client.h"

#include <zmq.hpp>
#include <nlohmann/json.hpp>

#include <string>

class TestbedProxy;

class ServiceProxy
{
public:
	ServiceProxy(std::shared_ptr<TestbedProxy> testbed, std::string service_id);
	virtual ~ServiceProxy();

	Value GetProperty(const std::string &name, void (*error_check)() = nullptr);
	Value SetProperty(const std::string &name, const Value &value, void (*error_check)() = nullptr);

	Value ExecuteCommand(const std::string &name, const Dict &arguments, void (*error_check)() = nullptr);

	std::shared_ptr<DataStream> GetDataStream(const std::string &name, void (*error_check)() = nullptr);

	std::shared_ptr<DataStream> GetHeartbeat();

	ServiceState GetState();
	bool IsRunning();
	bool IsAlive();

	void Start(double timeout_in_sec = -1, void (*error_check)() = nullptr);
	void Stop();
	void Interrupt();
	void Terminate();

	std::vector<std::string> GetPropertyNames(void (*error_check)() = nullptr);
	std::vector<std::string> GetCommandNames(void (*error_check)() = nullptr);
	std::vector<std::string> GetDataStreamNames(void (*error_check)() = nullptr);

	nlohmann::json GetConfig();

private:
	void Connect();
	void Disconnect();

	std::shared_ptr<TestbedProxy> m_Testbed;
	std::string m_ServiceId;

	std::unique_ptr<Client> m_Client;

	std::vector<std::string> m_PropertyNames;
	std::vector<std::string> m_CommandNames;
	std::map<std::string, std::string> m_DataStreamIds;

	std::map<std::string, std::shared_ptr<DataStream>> m_DataStreams;

	std::shared_ptr<DataStream> m_Heartbeat;
	std::shared_ptr<DataStream> m_State;
	std::uint64_t m_TimeLastConnect;
};

#endif // SERVICE_PROXY_H
