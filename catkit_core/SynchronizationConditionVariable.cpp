#include "SynchronizationConditionVariable.h"

#include "Timing.h"

#if defined(__linux__) || defined(__APPLE__)

void SynchronizationConditionVariable::Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)())
{
    Timer timer;

	while (!condition())
	{
		// Wait for a maximum of 20ms to perform periodic error checking.
		long timeout_wait = std::min(20L, timeout_in_ms);

#ifdef __APPLE__
		// Relative timespec.
		timespec timeout;
		timeout.tv_sec = timeout_wait / 1000;
		timeout.tv_nsec = 1000000 * (timeout_wait % 1000);

		int res = pthread_cond_timedwait_relative_np(&(m_SharedState->m_Condition), &(m_SharedState->m_Mutex), &timeout);
#else
		// Absolute timespec.
		timespec timeout;
		clock_gettime(CLOCK_MONOTONIC, &timeout);
		timeout.tv_sec += timeout_wait / 1000;
		timeout.tv_nsec += 1000000 * (timeout_wait % 1000);

		int res = pthread_cond_timedwait(&(m_SharedState->m_Condition), &(m_SharedState->m_Mutex), &timeout);
#endif // __APPLE__
		if (res == ETIMEDOUT && timer.GetTime() > (timeout_in_ms * 0.001))
		{
			throw std::runtime_error("Waiting time has expired.");
		}

		if (error_check != nullptr)
			error_check();
	}
}

void SynchronizationConditionVariable::Signal()
{
    pthread_cond_broadcast(&(m_SharedState->m_Condition));
}

void SynchronizationConditionVariable::Lock()
{
    pthread_mutex_lock(&(m_SharedState->m_Mutex));
}

void SynchronizationConditionVariable::Unlock()
{
    pthread_mutex_unlock(&(m_SharedState->m_Mutex));
}

void SynchronizationConditionVariable::CreateImpl(const std::string &id, SynchronizationConditionVariable::SharedState *shared_state)
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

#endif
