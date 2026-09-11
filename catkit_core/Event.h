#ifndef EVENT_H
#define EVENT_H

#include "EventBase.h"
#include "Shareable.h"

#include <string>
#include <memory>
#include <array>

enum class EventWaitMethod
{
	ConditionVariable,
	Futex,
	Semaphore,
	SpinLock,
#ifdef _WIN32
	Default = Semaphore
#elif defined(__linux__)
	Default = Futex
#elif defined(__APPLE__)
	Default = Futex
#endif
};

class Event : public Shareable
{
private:
	Event(std::shared_ptr<Memory> memory_block);

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
	void Wait(double timeout_in_sec, std::function<bool()> condition, EventWaitMethod wait_method = EventWaitMethod::Default, void (*error_check)() = nullptr);
	void Signal();

	static std::shared_ptr<Event> Create(StructStream &stream, std::string_view id);
	static std::shared_ptr<Event> Open(StructStream &stream);

	static constexpr std::size_t GetSharedStateSize()
	{
		return sizeof(Header);
	}

	ShareableType GetType() const override;

private:
	std::shared_ptr<EventConditionVariable> m_ConditionVariable;
	std::shared_ptr<EventFutex> m_Futex;
	std::shared_ptr<EventSemaphore> m_Semaphore;
	std::shared_ptr<EventSpinLock> m_SpinLock;
};

#endif // EVENT_H
