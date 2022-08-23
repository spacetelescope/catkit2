#ifndef SERVICE_PROXY_H
#define SERVICE_PROXY_H

#include "Types.h"
#include "DataStream.h"
#include "ServiceState.h"
#include "Client.h"

#include <zmq.hpp>

#include <string>

class TestbedProxy;

class ServiceProxy
{
public:
	ServiceProxy(std::shared_ptr<TestbedProxy> testbed, std::string service_id);
	virtual ~ServiceProxy();

	Value GetProperty(const std::string &name);
	Value SetProperty(const std::string &name, const Value &value);

	Value ExecuteCommand(const std::string &name, const Dict &arguments);

	std::shared_ptr<DataStream> GetDataStream(const std::string &name);

	std::shared_ptr<DataStream> GetHeartbeat();

	ServiceState GetState();
	bool IsRunning();
	bool IsAlive();

	void Start();
	void Stop();
	void Interrupt();
	void Terminate();

	void WaitUntilRunning(double timeout_in_sec, void (*error_check)() = nullptr);

private:
	void Connect();

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
