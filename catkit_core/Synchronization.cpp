#include "Synchronization.h"

#include <stdexcept>
#include <algorithm>


#ifndef _WIN32
	#include <errno.h>
#endif

#include "TimeStamp.h"

Synchronization::Synchronization()
	: m_IsOwner(false), m_SharedData(nullptr)
{
}

Synchronization::~Synchronization()
{
	if (m_SharedData)
	{
#ifdef _WIN32
		CloseHandle(m_Semaphore);
#else

#endif
	}
}

void Synchronization::Initialize(const std::string &id, SynchronizationSharedData *shared_data, bool create)
{
	if (create)
	{
		Create(id, shared_data);
	}
	else
	{
		Open(id, shared_data);
	}
}

void Synchronization::Create(const std::string &id, SynchronizationSharedData *shared_data)
{
	if (m_SharedData)
		throw std::runtime_error("Create called on an already initialized Synchronization object.");

	if (!shared_data)
		throw std::runtime_error("The passed shared data was a nullptr.");

#ifdef _WIN32
	m_Semaphore = CreateSemaphore(NULL, 0, 9999, (id + ".sem").c_str());

	if (m_Semaphore == NULL)
		throw std::runtime_error("Something went wrong while creating semaphore.");

	shared_data->m_NumReadersWaiting = 0;
#else
	pthread_mutexattr_t mutex_attr = {};
	pthread_mutexattr_setpshared(&mutex_attr, PTHREAD_PROCESS_SHARED);
	pthread_mutex_init(&(shared_data->m_Mutex), &mutex_attr);

	pthread_condattr_t cond_attr = {};
	pthread_condattr_setpshared(&cond_attr, PTHREAD_PROCESS_SHARED);
#ifndef __APPLE__
	pthread_condattr_setclock(&cond_attr, CLOCK_MONOTONIC);
#endif
	pthread_cond_init(&(shared_data->m_Condition), &cond_attr);
#endif

	m_SharedData = shared_data;
}

void Synchronization::Open(const std::string &id, SynchronizationSharedData *shared_data)
{
	if (m_SharedData)
		throw std::runtime_error("Open called on an already initialized Synchronization object.");

	if (!shared_data)
		throw std::runtime_error("The passed shared data was a nullptr.");

#ifdef _WIN32
	HANDLE semaphore = OpenSemaphore(SEMAPHORE_ALL_ACCESS, FALSE, (id + ".sem").c_str());

	if (semaphore == NULL)
		throw std::runtime_error("Something went wrong while opening semaphore.");

#else
#endif

	m_SharedData = shared_data;
}

void Synchronization::Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)())
{
	if (!m_SharedData)
		throw std::runtime_error("Wait() was called before the synchronization was intialized.");

#ifdef _WIN32
	TimeDelta timer;
	DWORD res = WAIT_OBJECT_0;

	while (!condition())
	{
		if (res == WAIT_OBJECT_0)
		{
			// Increment the number of readers that are waiting, making sure the counter
			// is at least 1 after the increment. This can occur when a previous reader got
			// interrupted and the trigger happening before decrementing the
			// m_NumReadersWaiting counter.
			while (m_SharedData->m_NumReadersWaiting++ < 0)
			{
			}
		}

		// Wait for a maximum of 20ms to perform periodic error checking.
		auto res = WaitForSingleObject(m_Semaphore, (unsigned long) std::min(20, timeout_in_ms));

		if (res == WAIT_TIMEOUT && timer.GetTimeDelta() > (timeout_in_ms * 0.001))
		{
			m_SharedData->m_NumReadersWaiting--;
			throw std::runtime_error("Waiting time has expired.");
		}

		if (error_check != nullptr)
		{
			try
			{
				error_check();
			}
			catch (...)
			{
				m_SharedData->m_NumReadersWaiting--;
				throw;
			}
		}
	}
#else
	TimeDelta timer;

	pthread_mutex_lock(&(m_SharedData->m_Mutex));

	while (!condition())
	{
		// Wait for a maximum of 20ms to perform periodic error checking.
		long timeout_wait = std::min(20L, timeout_in_ms);

#ifdef __APPLE__
		// Relative timespec.
		timespec timeout;
		timeout.tv_sec = timeout_wait / 1000;
		timeout.tv_nsec = 1000000 * (timeout_wait % 1000);
		
		int res = pthread_cond_timedwait_relative_np(&(m_SharedData->m_Condition), &(m_SharedData->m_Mutex), &timeout);
#else

		// Absolute timespec.
		timespec timeout;
		clock_gettime(CLOCK_MONOTONIC, &timeout);
		timeout.tv_sec += timeout_wait / 1000;
		timeout.tv_nsec += 10000000 * (timeout_wait % 1000);

		int res = pthread_cond_timedwait(&(m_SharedData->m_Condition), &(m_SharedData->m_Mutex), &timeout);
#endif
		if (res == ETIMEDOUT && timer.GetTimeDelta() > (timeout_in_ms * 0.001))
		{
			pthread_mutex_unlock(&(m_SharedData->m_Mutex));
			throw std::runtime_error("Waiting time has expired.");
		}

		if (error_check != nullptr)
		{
			try
			{
				error_check();
			}
			catch (...)
			{
				pthread_mutex_unlock(&(m_SharedData->m_Mutex));
				throw;
			}
		}
	}
	pthread_mutex_unlock(&(m_SharedData->m_Mutex));
#endif
}

void Synchronization::Signal()
{
	if (!m_SharedData)
		throw std::runtime_error("Signal() was called before the synchronization was intialized.");

#ifdef _WIN32
	// Notify waiting processes.
	long num_readers_waiting = m_SharedData->m_NumReadersWaiting.exchange(0);

	// If a reader times out in between us reading the number of readers that are waiting
	// and us releasing the semaphore, we are releasing one too many readers. This
	// results in a future reader being released immediately, which is not a problem,
	// as there are checks in place for that.

	if (num_readers_waiting > 0)
		ReleaseSemaphore(m_Semaphore, (LONG) num_readers_waiting, NULL);
#else
	pthread_cond_broadcast(&(m_SharedData->m_Condition));
#endif
}
