#ifndef SERVICE_STATE_H
#define SERVICE_STATE_H

#include "testbed.pb.h"

using ServiceState = catkit_proto::testbed::ServiceState;

bool IsAliveState(const ServiceState &state);

#endif // SERVICE_STATE_H