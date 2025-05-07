#include "Event.h"

void Event::Wait(double timeout_in_sec, std::function<bool()> condition, EventWaitMethod wait_method, void (*error_check)())
{
	// Set default wait method.
	if (wait_method == EventWaitMethod::Default)
	{
		#ifdef _WIN32
		wait_method = EventWaitMethod::Semaphore;
		#elif defined(__linux__) || defined(__APPLE__)
		wait_method = EventWaitMethod::ConditionVariable;
		#endif
	}

	// Wait for a specific event type.
	switch (wait_method)
	{
		case EventWaitMethod::ConditionVariable:
			m_ConditionVariable->Wait(timeout_in_sec, condition, error_check);
			break;
		case EventWaitMethod::Futex:
			m_Futex->Wait(timeout_in_sec, condition, error_check);
			break;
		case EventWaitMethod::Semaphore:
			m_Semaphore->Wait(timeout_in_sec, condition, error_check);
			break;
		case EventWaitMethod::SpinLock:
			m_SpinLock->Wait(timeout_in_sec, condition, error_check);
			break;
		default:
			throw std::runtime_error("Unknown wait method.");
	}
}

void Event::Signal()
{
	// Signal all event types.
	m_SpinLock->Signal();
	m_Futex->Signal();
	m_Semaphore->Signal();
	m_ConditionVariable->Signal();
}

void Event::Lock()
{
	// Lock all event types.
	m_SpinLock->Lock();
	m_Futex->Lock();
	m_Semaphore->Lock();
	m_ConditionVariable->Lock();
}

void Event::Unlock()
{
	// Unlock all event types.
	m_Semaphore->Unlock();
	m_Futex->Unlock();
	m_SpinLock->Unlock();
	m_ConditionVariable->Unlock();
}

std::shared_ptr<Event> Event::Create(StructStream &stream, std::string_view id)
{
	auto header = stream.Extract<Header>();

	header->m_Id.fill('\0');
	id.copy(header->m_Id.data(), EVENT_ID_MAX_SIZE - 1);

	auto event = std::shared_ptr<Event>(new Event());

	// Create all event types.
	event->m_ConditionVariable = EventConditionVariable::Create(id, &header->m_ConditionVariable);
	event->m_Futex = EventFutex::Create(id, &header->m_Futex);
	event->m_Semaphore = EventSemaphore::Create(id, &header->m_Semaphore);
	event->m_SpinLock = EventSpinLock::Create(id, &header->m_SpinLock);

	return event;
}

std::shared_ptr<Event> Event::Open(StructStream &stream)
{
	std::shared_ptr<Event> event(new Event());

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
