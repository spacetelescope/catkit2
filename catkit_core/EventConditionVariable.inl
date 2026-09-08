#include "EventBase.h"

#include "Timing.h"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <string>

#if defined(__linux__) || defined(__APPLE__)
	#include <pthread.h>
#endif

using EventConditionVariable = EventImpl<EventImplementationType::ConditionVariable>;

#if defined(__linux__) || defined(__APPLE__)

template<>
struct is_event_implemented<EventImplementationType::ConditionVariable> : std::true_type
{
};

template<>
struct EventSharedState<EventImplementationType::ConditionVariable>
{
	pthread_mutex_t m_Mutex;
	pthread_cond_t m_Condition;
};

class PThreadLockGuard
{
public:
	inline PThreadLockGuard(pthread_mutex_t *mutex)
		: m_Mutex(mutex)
	{
		pthread_mutex_lock(m_Mutex);
	}

	inline ~PThreadLockGuard()
	{
		pthread_mutex_unlock(m_Mutex);
	}

private:
	pthread_mutex_t *m_Mutex;
};

// Note on macOS: Apple's libpthread stores the address of the mutex used by the first waiter
// inside the condition variable ("cond->busy") and returns EINVAL, without releasing the mutex,
// to any subsequent waiter that passes the same mutex mapped at a different virtual address.
// Since every process maps the shared memory at a different address, this implementation
// cannot be used for cross-process synchronization on macOS and is therefore not the default
// there (see Event.h). The error is reported as an exception rather than silently retried, as
// retrying would spin while holding the mutex and block all signaling processes.
template<>
inline void EventConditionVariable::Wait(double timeout_in_sec, std::function<bool()> condition, void (*error_check)())
{
	Timer timer;
	auto lock = PThreadLockGuard(&m_SharedState->m_Mutex);

	while (!condition())
	{
		// Wait for a maximum of 20ms to perform periodic error checking.
		double time_remaining = timeout_in_sec - timer.GetTime();
		double timeout_wait = std::min(0.020, time_remaining);

		if (timeout_wait <= 0)
		{
			// The timeout expired.
			throw std::runtime_error("Waiting time has expired.");
		}

#ifdef __APPLE__
		// Relative timespec.
		timespec timeout;
		timeout.tv_sec = static_cast<time_t>(timeout_wait);
		timeout.tv_nsec = 1'000'000'000 * (timeout_wait - static_cast<time_t>(timeout_wait));

		if (timeout.tv_nsec >= 1'000'000'000)
		{
			timeout.tv_sec += 1;
			timeout.tv_nsec -= 1'000'000'000;
		}

		int res = pthread_cond_timedwait_relative_np(&(m_SharedState->m_Condition), &(m_SharedState->m_Mutex), &timeout);
#else
		// Absolute timespec.
		timespec timeout;
		clock_gettime(CLOCK_MONOTONIC, &timeout);
		timeout.tv_sec += static_cast<time_t>(timeout_wait);
		timeout.tv_nsec += 1'000'000'000 * (timeout_wait - static_cast<time_t>(timeout_wait));

		if (timeout.tv_nsec >= 1'000'000'000)
		{
			timeout.tv_sec += 1;
			timeout.tv_nsec -= 1'000'000'000;
		}

		int res = pthread_cond_timedwait(&(m_SharedState->m_Condition), &(m_SharedState->m_Mutex), &timeout);
#endif // __APPLE__

		// Both a wakeup (spurious or not) and a timeout lead to re-checking the condition.
		// Anything else is a genuine error; the lock guard releases the mutex when throwing.
		if (res != 0 && res != ETIMEDOUT)
		{
			throw std::runtime_error("Condition variable wait failed: " + std::string(std::strerror(res)));
		}

		if (error_check != nullptr)
			error_check();
	}
}

template<>
inline void EventConditionVariable::Signal()
{
	auto lock = PThreadLockGuard(&m_SharedState->m_Mutex);

	pthread_cond_broadcast(&(m_SharedState->m_Condition));
}

template<>
inline void EventConditionVariable::CreateImpl(std::string_view id, EventConditionVariable::SharedState *shared_state)
{
	pthread_mutexattr_t mutex_attr;
	pthread_mutexattr_init(&mutex_attr);
	pthread_mutexattr_setpshared(&mutex_attr, PTHREAD_PROCESS_SHARED);
	pthread_mutex_init(&(shared_state->m_Mutex), &mutex_attr);
	pthread_mutexattr_destroy(&mutex_attr);

	pthread_condattr_t cond_attr;
	pthread_condattr_init(&cond_attr);
	pthread_condattr_setpshared(&cond_attr, PTHREAD_PROCESS_SHARED);
#ifndef __APPLE__
	pthread_condattr_setclock(&cond_attr, CLOCK_MONOTONIC);
#endif // __APPLE__
	pthread_cond_init(&(shared_state->m_Condition), &cond_attr);
	pthread_condattr_destroy(&cond_attr);
}

template<>
inline void EventConditionVariable::OpenImpl(std::string_view id, EventConditionVariable::SharedState *shared_state)
{
	// Nothing to do.
}

#endif
