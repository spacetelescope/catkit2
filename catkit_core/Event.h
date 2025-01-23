#ifndef EVENT_H
#define EVENT_H

#include "EventBase.h"

// Select which implementation to use based on the platform.
#ifdef _WIN32
using Event = EventImpl<EventImplementationType::ET_SEMAPHORE>;
#else
using Event = EventImpl<EventImplementationType::ET_CONDITION_VARIABLE>;
#endif

#endif // EVENT_H
