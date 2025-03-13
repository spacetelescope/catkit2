#include "Event.h"

#include <array>

const int EVENT_ID_MAX_SIZE = 256;

struct Header
{
	std::array<char, EVENT_ID_MAX_SIZE> m_Id;

	EventConditionVariable::SharedState m_ConditionVariable;
	EventFutex::SharedState m_Futex;
	EventSemaphore::SharedState m_Semaphore;
	EventSpinLock::SharedState m_SpinLock;
};

Event::Event()
{
}

void Event::Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)())
{
	// Wait for a specific event type.
	#ifdef _WIN32
	m_Semaphore->Wait(timeout_in_ms, condition, error_check);
	#elif defined(__linux__) || defined(__APPLE__)
	m_ConditionVariable->Wait(timeout_in_ms, condition, error_check);
	#endif
}

void Event::Wait(long timeout_in_ms, std::function<bool()> condition, EventImplementationType event_type, void (*error_check)())
{
	// Wait for a specific event type.
	switch (event_type)
	{
		case EventImplementationType::ConditionVariable:
			m_ConditionVariable->Wait(timeout_in_ms, condition, error_check);
			break;
		case EventImplementationType::Futex:
			m_Futex->Wait(timeout_in_ms, condition, error_check);
			break;
		case EventImplementationType::Semaphore:
			m_Semaphore->Wait(timeout_in_ms, condition, error_check);
			break;
		case EventImplementationType::SpinLock:
			m_SpinLock->Wait(timeout_in_ms, condition, error_check);
			break;
		default:
			throw std::runtime_error("Unknown event type.");
	}
}

void Event::Signal()
{
	// Signal all event types.
	m_ConditionVariable->Signal();
	m_Futex->Signal();
	m_Semaphore->Signal();
	m_SpinLock->Signal();
}

void Event::Lock()
{
	// Lock all event types.
	m_ConditionVariable->Lock();
	m_Futex->Lock();
	m_Semaphore->Lock();
	m_SpinLock->Lock();
}

void Event::Unlock()
{
	// Unlock all event types.
	m_ConditionVariable->Unlock();
	m_Futex->Unlock();
	m_Semaphore->Unlock();
	m_SpinLock->Unlock();
}

std::unique_ptr<Event> Event::Create(StructStream &stream, std::string_view id)
{
	auto header = stream.Extract<Header>();

	header->m_Id.fill('\0');
	id.copy(header->m_Id.data(), EVENT_ID_MAX_SIZE - 1);

	auto event = std::unique_ptr<Event>(new Event());

	// Create all event types.
	event->m_ConditionVariable = EventConditionVariable::Create(id, &header->m_ConditionVariable);
	event->m_Futex = EventFutex::Create(id, &header->m_Futex);
	event->m_Semaphore = EventSemaphore::Create(id, &header->m_Semaphore);
	event->m_SpinLock = EventSpinLock::Create(id, &header->m_SpinLock);

	return event;
}

std::unique_ptr<Event> Event::Open(StructStream &stream)
{
	std::unique_ptr<Event> event(new Event());

	auto header = stream.Extract<Header>();

	auto id = std::string(header->m_Id.data());

	// Open all event types.
	event->m_ConditionVariable = EventConditionVariable::Open(id, &header->m_ConditionVariable);
	event->m_Futex = EventFutex::Open(id, &header->m_Futex);
	event->m_Semaphore = EventSemaphore::Open(id, &header->m_Semaphore);
	event->m_SpinLock = EventSpinLock::Open(id, &header->m_SpinLock);

	return event;
}

ShareableType Event::GetType() const
{
	return ShareableType::Event;
}

constexpr std::size_t Event::GetSharedStateSize()
{
	return sizeof(Header);
}
