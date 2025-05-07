#ifndef EVENT_BASE_H
#define EVENT_BASE_H

#include <functional>
#include <stdexcept>
#include <memory>
#include <string_view>

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
	static std::shared_ptr<EventImpl<Type>> Create(std::string_view id, SharedState *shared_state);
	static std::shared_ptr<EventImpl<Type>> Open(std::string_view id, SharedState *shared_state);

	// Note: implement the following functions for specific implementations.
	inline void Wait(double timeout_in_sec, std::function<bool()> condition, void (*error_check)());
	inline void Signal();

	inline void Lock();
	inline void Unlock();

protected:
	inline void CreateImpl(std::string_view id, SharedState *shared_state);
	inline void OpenImpl(std::string_view id, SharedState *shared_state);

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
