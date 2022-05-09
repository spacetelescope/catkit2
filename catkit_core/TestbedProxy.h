#ifndef TESTBED_PROXY_H
#define TESTBED_PROXY_H

#include "ServiceProxy.h"
#include "LoggingProxy.h"
#include "DataStream.h"
#include "Client.h"
#include "server.pb.h"

#include <zmq.hpp>
#include <nlohmann/json.hpp>

#include <string>
#include <mutex>

using ServiceState = catkit_proto::ServiceState;

struct ServiceReference
{
	std::string id;
	std::string type;
	ServiceState state;
	std::string host;
	unsigned long port;
};

class TestbedProxy : public Client
{
public:
	TestbedProxy(std::string host, int port);
	~TestbedProxy();

	std::shared_ptr<ServiceProxy> GetService(const std::string &service_id);

	void RequireService(const std::string &service_id);
	void RequireServices(std::vector<std::string> service_ids);

	ServiceState GetServiceState(const std::string &service_id);

	void RegisterService(std::string service_id, std::string service_type, int port);
	void UpdateServiceState(std::string service_id, ServiceState new_state);

	bool IsSimulated();
	bool IsAlive();

	std::string GetExperimentPath();
	std::string StartNewExperiment(std::string experiment_name, nlohmann::json metadata);
	nlohmann::json GetConfig();

	std::string GetHost();
	int GetLoggingEgressPort();
	int GetTracingIngressPort();

	std::vector<std::string> GetActiveServices();
	std::vector<std::string> GetInactiveServices();

private:
	template<typename ProtoRequest, typename ProtoReply>
	void MakeRequest(std::string what, const ProtoRequest &request, ProtoReply &reply);

	void GetServerInfo();

	std::string m_Host;
	int m_TestbedPort;

	int m_LoggingIngressPort;
	int m_LoggingEgressPort;

	int m_DataLoggingIngressPort;
	int m_TracingIngressPort;

	zmq::socket_t GetSocket();

	bool m_HasGottenInfo;

	std::shared_ptr<DataStream> m_HeartbeatStream;

	bool m_IsSimulated;
	nlohmann::json m_Config;
};

#endif // TESTBED_PROXY_H
