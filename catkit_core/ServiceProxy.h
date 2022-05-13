#ifndef SERVICE_PROXY_H
#define SERVICE_PROXY_H

#include "Types.h"
#include "TestbedProxy.h"

#include <zmq.hpp>

#include <string>

class ServiceProxy
{
public:
	ServiceProxy(std::shared_ptr<TestbedProxy> testbed, std::string service_id);
	~ServiceProxy();

	Value GetProperty(const std::string &name);
	Value SetProperty(const std::string &name, const Value &value);

	Value ExecuteCommand(const Dict &arguments);

	std::shared_ptr<DataStream> GetDataStream(const std::string &name);

	ServiceState GetState();
	bool IsAlive();

	void Start();
	void Stop();

private:
	std::shared_ptr<TestbedProxy> m_Testbed;
	std::string m_ServiceId;

	zmq::socket_t GetSocket();

	std::vector<std::string> m_PropertyNames;
	std::vector<std::string> m_CommandNames;
	std::map<std::string, std::string> m_DataStreamIds;

	std::map<std::string, std::shared_ptr<DataStream>> m_DataStreams;

	std::shared_ptr<DataStream> m_HeartbeatStream;
	ServiceState m_LastKnownState;
};

#endif // SERVICE_PROXY_H