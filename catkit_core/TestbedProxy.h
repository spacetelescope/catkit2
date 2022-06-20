#ifndef TESTBED_PROXY_H
#define TESTBED_PROXY_H

#include "ServiceProxy.h"
#include "LoggingProxy.h"
#include "DataStream.h"
#include "Communication.h"
#include "testbed.pb.h"
#include "ServiceState.h"

#include <zmq.hpp>
#include <nlohmann/json.hpp>

#include <string>
#include <mutex>

struct ServiceReference
{
	std::string id;
	std::string type;
	ServiceState state;
	std::string host;
	unsigned long port;
};

class TestbedProxy : public Client, public std::enable_shared_from_this<TestbedProxy>
{
public:
	TestbedProxy(std::string host, int port);
	virtual ~TestbedProxy();

	std::shared_ptr<ServiceProxy> GetService(const std::string &service_id);

	void StartService(const std::string &service_id);
	void StartServices(std::vector<std::string> service_ids);

	void StopService(const std::string &service_id);

	ServiceReference GetServiceInfo(const std::string &service_id);
	ServiceState GetServiceState(const std::string &service_id);

	void RegisterService(std::string service_id, std::string service_type, int port);
	void UpdateServiceState(std::string service_id, ServiceState new_state);

	bool IsSimulated();
	bool IsAlive();

	nlohmann::json GetConfig();

	std::string GetHost();
	int GetLoggingEgressPort();
	int GetTracingIngressPort();

	std::vector<std::string> GetActiveServices();
	std::vector<std::string> GetInactiveServices();

private:
	void GetServerInfo();

	std::string m_Host;

	int m_LoggingIngressPort;
	int m_LoggingEgressPort;

	int m_DataLoggingIngressPort;
	int m_TracingIngressPort;

	bool m_HasGottenInfo;

	std::shared_ptr<DataStream> m_HeartbeatStream;

	bool m_IsSimulated;
	nlohmann::json m_Config;

	std::map<std::string, std::shared_ptr<ServiceProxy>> m_Services;
};

#endif // TESTBED_PROXY_H
