#include "Event.h"

Event::Event(SharedState *shared_state)
	: ShareableImpl(shared_state)
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

std::unique_ptr<Event> Event::Create(std::string id, SharedState *shared_state)
{
	std::unique_ptr<Event> event(new Event(shared_state));

	// Create all event types.
	event->m_ConditionVariable = EventConditionVariable::Create(id, &shared_state->m_ConditionVariable);
	event->m_Futex = EventFutex::Create(id, &shared_state->m_Futex);
	event->m_Semaphore = EventSemaphore::Create(id, &shared_state->m_Semaphore);
	event->m_SpinLock = EventSpinLock::Create(id, &shared_state->m_SpinLock);

	return event;
}

std::unique_ptr<Event> Event::Open(std::string id, SharedState *shared_state)
{
	std::unique_ptr<Event> event(new Event(shared_state));

	// Open all event types.
	event->m_ConditionVariable = EventConditionVariable::Open(id, &shared_state->m_ConditionVariable);
	event->m_Futex = EventFutex::Open(id, &shared_state->m_Futex);
	event->m_Semaphore = EventSemaphore::Open(id, &shared_state->m_Semaphore);
	event->m_SpinLock = EventSpinLock::Open(id, &shared_state->m_SpinLock);

	return event;
}
