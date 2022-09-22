#include "ServiceState.h"

bool IsAliveState(const ServiceState &state)
{
    return state == ServiceState::INITIALIZING
		|| state == ServiceState::OPENING
		|| state == ServiceState::RUNNING;
}
