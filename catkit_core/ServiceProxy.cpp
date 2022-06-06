#include "ServiceProxy.h"

#include "TestbedProxy.h"
#include "Service.h"

using namespace std::string_literals;

ServiceProxy::ServiceProxy(std::shared_ptr<TestbedProxy> testbed, std::string service_id)
	: m_Testbed(testbed), m_ServiceId(service_id)
{
	// Do a check to see if the service id is correct.
	auto testbed_config = testbed->GetConfig();

	if (!testbed_config["services"].contains(service_id))
	{
		throw std::runtime_error("Service "s + service_id + " is a non-existant service id.");
	}
}

ServiceProxy::~ServiceProxy()
{
}

Value ServiceProxy::GetProperty(const std::string &name)
{
	if (!IsAlive())
		throw std::runtime_error("Cannot get a property from a dead service.");

	return Value();
}

Value ServiceProxy::SetProperty(const std::string &name, const Value &value)
{
	if (!IsAlive())
		throw std::runtime_error("Cannot set a property on a dead service.");

	return Value();
}

Value ServiceProxy::ExecuteCommand(const std::string &name, const Dict &arguments)
{
	if (!IsAlive())
		throw std::runtime_error("Cannot execute a command on a dead service.");

	return Value();
}

std::shared_ptr<DataStream> ServiceProxy::GetDataStream(const std::string &name)
{
	if (!IsAlive())
		throw std::runtime_error("Cannot get a data stream from a dead service.");

	return nullptr;
}

ServiceState ServiceProxy::GetState()
{
	if (m_HeartbeatStream)
	{
		// Check heartbeat stream.
		std::uint64_t heartbeat_time = m_HeartbeatStream->GetLatestFrame().AsArray<std::uint64_t>()(0);
		std::uint64_t current_time = GetTimeStamp();

		if ((current_time - heartbeat_time) / 1e9 < SERVICE_LIVELINESS)
			return ServiceState::OPERATIONAL;
	}

	auto state = m_Testbed->GetServiceState(m_ServiceId);

	// Connect if the service became operational.
	if (m_LastKnownState != ServiceState::OPERATIONAL && state == ServiceState::OPERATIONAL)
		Connect();

	m_LastKnownState = state;

	return state;
}

bool ServiceProxy::IsRunning()
{
	auto state = GetState();
	return GetState() == ServiceState::OPERATIONAL;
}

void ServiceProxy::Start()
{
	if (IsAlive())
		return;


}

void ServiceProxy::Stop()
{
	if (!IsAlive())
		return;


}

void ServiceProxy::WaitUntilRunning()
{
}

void ServiceProxy::Connect()
{
}
