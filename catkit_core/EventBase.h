#ifndef EVENT_BASE_H
#define EVENT_BASE_H

#include <functional>

enum EventImplementationType
{
	ET_CONDITION_VARIABLE,
	ET_FUTEX,
	ET_SEMAPHORE,
	ET_SPIN_LOCK
};

template<EventImplementationType Type>
struct EventSharedState
{
};

template<EventImplementationType Type>
struct EventLocalState
{
};

template<EventImplementationType Type>
class EventImpl
{
public:
	using SharedState = EventSharedState<Type>;
	using LocalState = EventLocalState<Type>;

protected:
	EventImpl();

public:
	~EventImpl();

	static std::unique_ptr<EventImpl<Type>> Create(const std::string &id, SharedState *shared_state);
	static std::unique_ptr<EventImpl<Type>> Open(const std::string &id, SharedState *shared_state);

	void Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)());
	void Signal();

	void Lock();
	void Unlock();

protected:
	void CreateImpl(const std::string &id, SharedState *shared_state);
	void OpenImpl(const std::string &id, SharedState *shared_state);

	bool m_IsOwner;

	SharedState *m_SharedState;
	LocalState m_LocalState;
};

template<enum EventImplementationType Type>
EventImpl<Type>::EventImpl()
	: m_IsOwner(false), m_SharedState(nullptr)
{
}

template<enum EventImplementationType Type>
EventImpl<Type>::~EventImpl()
{
}

template<enum EventImplementationType Type>
void EventImpl<Type>::Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)())
{
	throw std::runtime_error("This type of event implementation wasn't implemented.");
}

template<enum EventImplementationType Type>
void EventImpl<Type>::Signal()
{
}

template<enum EventImplementationType Type>
void EventImpl<Type>::Lock()
{
}

template<enum EventImplementationType Type>
void EventImpl<Type>::Unlock()
{
}

template<enum EventImplementationType Type>
void EventImpl<Type>::CreateImpl(const std::string &id, EventImpl<Type>::SharedState *shared_state)
{
	if (!shared_state)
		throw std::runtime_error("The passed shared data was a nullptr.");

	auto obj = std::make_shared<EventImpl<Type>>();

	obj->CreateImpl(id, shared_state);

	obj->m_IsOwner = true;

	obj->m_SharedState = shared_state;
}

template<enum EventImplementationType Type>
void EventImpl<Type>::OpenImpl(const std::string &id, EventImpl<Type>::SharedState *shared_state)
{
	if (!shared_state)
		throw std::runtime_error("The passed shared data was a nullptr.");

	OpenImpl(id, shared_state);

	m_IsOwner = false;

	m_SharedState = shared_state;
}

#include "EventConditionVariable.inl"
#include "EventFutex.inl"
#include "EventSemaphore.inl"
#include "EventSpinLock.inl"

#endif // EVENT_BASE_H
