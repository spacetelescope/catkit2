#ifndef EVENT_H
#define EVENT_H

#include "EventBase.h"

template <typename Event>
class EventLockGuard
{
public:
	inline EventLockGuard(Event &event)
		: m_Event(event)
	{
		m_Event->Lock();
	}

	inline ~EventLockGuard()
	{
		m_Event->Unlock();
	}

private:
	Event &m_Event;
};

// Select which implementation to use based on the platform.
#ifdef _WIN32
using Event = EventImpl<EventImplementationType::ET_SEMAPHORE>;
#elif defined(__linux__) or defined(__APPLE__)
using Event = EventImpl<EventImplementationType::ET_CONDITION_VARIABLE>;
#endif

#endif // EVENT_H
