#ifndef SERVICE_PROXY_V2_H
#define SERVICE_PROXY_V2_H

#include "Types.h"
#include "ServiceState.h"
#include "MessageBroker.h"

#include <zmq.hpp>
#include <nlohmann/json.hpp>

#include <string>
#include <cstdint>
#include <vector>

class TestbedProxy;

class ServiceProxyV2
{
public:
	ServiceProxyV2(std::shared_ptr<MessageBroker> broker, std::string service_id);
	virtual ~ServiceProxyV2();

	ArrayView GetProperty(const std::string &name);
	ArrayView SetProperty(const std::string &name, ArrayView array, void (*error_check)() = nullptr);

	ArrayView ExecuteMethod(const std::string &name, const Dict &arguments, void (*error_check)() = nullptr);

	ServiceState GetState();
	bool IsRunning();
	bool IsAlive();

	void Start(double timeout_in_sec = -1, void (*error_check)() = nullptr);
	void Stop();
	void Interrupt();
	void Terminate();

	std::vector<std::string> GetProperties();
	std::vector<std::string> GetMethods();

	nlohmann::json GetConfig();
	std::string GetId();

private:
	std::shared_ptr<MessageBroker> m_Broker;
	std::string m_ServiceId;
};

#endif // SERVICE_PROXY_V2_H
