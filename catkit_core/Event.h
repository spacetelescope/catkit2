#ifndef EVENT_H
#define EVENT_H

#include "EventBase.h"
#include "Shareable.h"

#include <string>
#include <memory>

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

class Event : public ShareableImpl<ShareableType::Event>
{
public:
	Event(SharedState *shared_state);

	void Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)() = nullptr);
	void Wait(long timeout_in_ms, std::function<bool()> condition, EventImplementationType event_type, void (*error_check)() = nullptr);
	void Signal();

	void Lock();
	void Unlock();

	static std::unique_ptr<Event> Create(std::string id, SharedState *shared_state);
	static std::unique_ptr<Event> Open(SharedState *shared_state);

private:
	std::unique_ptr<EventConditionVariable> m_ConditionVariable;
	std::unique_ptr<EventFutex> m_Futex;
	std::unique_ptr<EventSemaphore> m_Semaphore;
	std::unique_ptr<EventSpinLock> m_SpinLock;
};

const int EVENT_ID_MAX_SIZE = 256;

template<>
struct SharedState<ShareableType::Event>
{
	char m_Id[EVENT_ID_MAX_SIZE];

	EventConditionVariable::SharedState m_ConditionVariable;
	EventFutex::SharedState m_Futex;
	EventSemaphore::SharedState m_Semaphore;
	EventSpinLock::SharedState m_SpinLock;
};

#endif // EVENT_H
