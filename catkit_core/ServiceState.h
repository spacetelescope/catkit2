#ifndef SERVICE_STATE_H
#define SERVICE_STATE_H

#include "testbed.pb.h"

enum ServiceState
{
    CLOSED = 0,
    INITIALIZING = 1,
    OPENING = 2,
    RUNNING = 3,
    CLOSING = 4,
    UNRESPONSIVE = 5,
    CRASHED = 6
};

bool IsAliveState(const ServiceState &state);

#endif // SERVICE_STATE_H
