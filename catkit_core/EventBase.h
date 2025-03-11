#ifndef EVENT_BASE_H
#define EVENT_BASE_H

#include <functional>
#include <stdexcept>
#include <memory>

enum class EventImplementationType
{
	ConditionVariable,
	Futex,
	Semaphore,
	SpinLock
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

	// Note: do not implement these functions for specific implementations.
	static std::unique_ptr<EventImpl<Type>> Create(const std::string &id, SharedState *shared_state);
	static std::unique_ptr<EventImpl<Type>> Open(const std::string &id, SharedState *shared_state);

	// Note: implement the following functions for specific implementations.
	inline void Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)());
	inline void Signal();

	inline void Lock();
	inline void Unlock();

protected:
	inline void CreateImpl(const std::string &id, SharedState *shared_state);
	inline void OpenImpl(const std::string &id, SharedState *shared_state);

	bool m_IsOwner;

	SharedState *m_SharedState;
	LocalState m_LocalState;
};

#include "EventBase.inl"
#include "EventConditionVariable.inl"
#include "EventFutex.inl"
#include "EventSemaphore.inl"
#include "EventSpinLock.inl"

#endif // EVENT_BASE_H
