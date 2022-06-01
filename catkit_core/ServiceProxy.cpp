#include "ServiceProxy.h"

#include "TestbedProxy.h"

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
	return Value();
}

Value ServiceProxy::ExecuteCommand(const std::string &name, const Dict &arguments)
{
	return Value();
}

std::shared_ptr<DataStream> ServiceProxy::GetDataStream(const std::string &name)
{
	return nullptr;
}

ServiceState ServiceProxy::GetState()
{
	if (m_LastKnownState == ServiceState::OPERATIONAL)
	{

	}

	auto state = m_Testbed->GetServiceState(m_ServiceId);

	m_LastKnownState = state;

	return state;
}

bool ServiceProxy::IsAlive()
{
	if (m_LastKnownState)
		;
	auto state = GetState();

	return IsAliveState(state);
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
