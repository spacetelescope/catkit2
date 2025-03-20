#ifndef EVENT_H
#define EVENT_H

#include "EventBase.h"
#include "Shareable.h"

#include <string>
#include <memory>
#include <array>

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

enum class EventWaitMethod
{
	Default,
	ConditionVariable,
	Futex,
	Semaphore,
	SpinLock
};

class Event : public Shareable
{
private:
	static const int EVENT_ID_MAX_SIZE = 256;

	struct Header
	{
		std::array<char, EVENT_ID_MAX_SIZE> m_Id;

		EventConditionVariable::SharedState m_ConditionVariable;
		EventFutex::SharedState m_Futex;
		EventSemaphore::SharedState m_Semaphore;
		EventSpinLock::SharedState m_SpinLock;
	};

public:
	void Wait(long timeout_in_ms, std::function<bool()> condition, EventWaitMethod wait_method = EventWaitMethod::Default, void (*error_check)() = nullptr);
	void Signal();

	void Lock();
	void Unlock();

	static std::unique_ptr<Event> Create(StructStream &stream, std::string_view id);
	static std::unique_ptr<Event> Open(StructStream &stream);

	static constexpr std::size_t GetSharedStateSize()
	{
		return sizeof(Header);
	}

	ShareableType GetType() const override;

private:
	std::unique_ptr<EventConditionVariable> m_ConditionVariable;
	std::unique_ptr<EventFutex> m_Futex;
	std::unique_ptr<EventSemaphore> m_Semaphore;
	std::unique_ptr<EventSpinLock> m_SpinLock;
};

#endif // EVENT_H
