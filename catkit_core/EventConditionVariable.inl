#include "EventBase.h"

#include "Timing.h"

#include <string>

#if defined(__linux__) || defined(__APPLE__)
	#include <pthread.h>
#endif

using EventConditionVariable = EventImpl<EventImplementationType::ConditionVariable>;

#if defined(__linux__) || defined(__APPLE__)

template<>
struct EventSharedState<EventImplementationType::ConditionVariable>
{
	pthread_mutex_t m_Mutex;
	pthread_cond_t m_Condition;
};

template<>
inline void EventConditionVariable::Wait(double timeout_in_sec, std::function<bool()> condition, void (*error_check)())
{
    Timer timer;

	while (!condition())
	{
		// Wait for a maximum of 20ms to perform periodic error checking.
		double timeout_wait = std::min(0.020, timeout_in_sec);

#ifdef __APPLE__
		// Relative timespec.
		timespec timeout;
		timeout.tv_sec = static_cast<time_t>(timeout_wait);
		timeout.tv_nsec = 1'000'000'000 * (timeout_wait - static_cast<time_t>(timeout_wait));

		int res = pthread_cond_timedwait_relative_np(&(m_SharedState->m_Condition), &(m_SharedState->m_Mutex), &timeout);
#else
		// Absolute timespec.
		timespec timeout;
		clock_gettime(CLOCK_MONOTONIC, &timeout);
		timeout.tv_sec += static_cast<time_t>(timeout_wait);
		timeout.tv_nsec += 1'000'000'000 * (timeout_wait - static_cast<time_t>(timeout_wait));

		int res = pthread_cond_timedwait(&(m_SharedState->m_Condition), &(m_SharedState->m_Mutex), &timeout);
#endif // __APPLE__
		if (res == ETIMEDOUT && timer.GetTime() > timeout_in_sec)
		{
			throw std::runtime_error("Waiting time has expired.");
		}

		if (error_check != nullptr)
			error_check();
	}
}

template<>
inline void EventConditionVariable::Signal()
{
    pthread_cond_broadcast(&(m_SharedState->m_Condition));
}

template<>
inline void EventConditionVariable::Lock()
{
    pthread_mutex_lock(&(m_SharedState->m_Mutex));
}

template<>
inline void EventConditionVariable::Unlock()
{
    pthread_mutex_unlock(&(m_SharedState->m_Mutex));
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
