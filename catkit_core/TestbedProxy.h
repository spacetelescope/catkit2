#ifndef TESTBED_PROXY_H
#define TESTBED_PROXY_H

#include "ServiceProxy.h"
#include "LoggingProxy.h"
#include "DataStream.h"
#include "Client.h"
#include "proto/testbed.pb.h"
#include "ServiceState.h"
#include "Util.h"

#include <zmq.hpp>
#include <nlohmann/json.hpp>

#include <string>
#include <mutex>

struct ServiceReference
{
	std::string id;
	std::string type;
	std::string state_stream_id;
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

	void InterruptService(const std::string &service_id);
	void TerminateService(const std::string &service_id);

	ServiceReference GetServiceInfo(const std::string &service_id);

	std::string RegisterService(std::string service_id, std::string service_type, std::string host, int port, int process_id, std::string heartbeat_stream_id);

	bool IsSimulated();
	bool IsAlive();

	void ShutDown();

	std::shared_ptr<DataStream> GetHeartbeat();

	nlohmann::json GetConfig();

	std::string GetHost();
	int GetPort();

	int GetLoggingIngressPort();
	int GetLoggingEgressPort();

	int GetDataLoggingIngressPort();
	int GetDataLoggingEgressPort();

	int GetTracingIngressPort();
	int GetTracingEgressPort();

	std::string GetMode();

	std::vector<std::string> GetActiveServices();
	std::vector<std::string> GetInactiveServices();

	std::string GetBaseDataPath();
	std::string GetSupportDataPath();
	std::string GetLongTermMonitoringPath();

private:
	void GetTestbedInfo();

	std::string m_Host;
	int m_Port;

	int m_LoggingIngressPort;
	int m_LoggingEgressPort;

	int m_DataLoggingIngressPort;
	int m_DataLoggingEgressPort;

	int m_TracingIngressPort;
	int m_TracingEgressPort;

	bool m_HasGottenInfo;

	std::shared_ptr<DataStream> m_HeartbeatStream;

	bool m_IsSimulated;
	nlohmann::json m_Config;

	std::map<std::string, std::shared_ptr<ServiceProxy>> m_Services;
};

#endif // TESTBED_PROXY_H
