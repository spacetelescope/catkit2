#include "EventBase.h"

#include "Timing.h"

#ifdef _WIN32
	#define WIN32_LEAN_AND_MEAN
	#define NOMINMAX
	#include <windows.h>
#endif // _WIN32

using EventSemaphore = EventImpl<EventImplementationType::Semaphore>;

#ifdef _WIN32

template<>
struct EventSharedState<EventImplementationType::Semaphore>
{
	std::atomic_long m_NumReadersWaiting;
};

template<>
struct EventLocalState<EventImplementationType::Semaphore>
{
	HANDLE m_Semaphore;
};

template<>
inline void EventSemaphore::Wait(long timeout_in_ms, std::function<bool()> condition, void (*error_check)())
{
    Timer timer;
	DWORD res = WAIT_OBJECT_0;

	while (!condition())
	{
		if (res == WAIT_OBJECT_0)
		{
			// Increment the number of readers that are waiting, making sure the counter
			// is at least 1 after the increment. This can occur when a previous reader got
			// interrupted and the trigger happening before decrementing the
			// m_NumReadersWaiting counter.
			while (m_SharedState->m_NumReadersWaiting++ < 0)
			{
			}
		}

		// Wait for a maximum of 20ms to perform periodic error checking.
		res = WaitForSingleObject(m_LocalState.m_Semaphore, (unsigned long) (std::min)(20L, timeout_in_ms));

		if (res == WAIT_TIMEOUT && timer.GetTime() > (timeout_in_ms * 0.001))
		{
			m_SharedState->m_NumReadersWaiting--;
			throw std::runtime_error("Waiting time has expired.");
		}

		if (res == WAIT_FAILED)
		{
			m_SharedState->m_NumReadersWaiting--;
			throw std::runtime_error("An error occured during waiting for the semaphore: " + std::to_string(GetLastError()));
		}

		if (error_check != nullptr)
		{
			try
			{
				error_check();
			}
			catch (...)
			{
				m_SharedState->m_NumReadersWaiting--;
				throw;
			}
		}
	}
}

template<>
inline void EventSemaphore::Signal()
{
    // Notify waiting processes.
	long num_readers_waiting = m_SharedState->m_NumReadersWaiting.exchange(0);

	// If a reader times out in between us reading the number of readers that are waiting
	// and us releasing the semaphore, we are releasing one too many readers. This
	// results in a future reader being released immediately, which is not a problem,
	// as there are checks in place for that.

	if (num_readers_waiting > 0)
		ReleaseSemaphore(m_LocalState.m_Semaphore, (LONG) num_readers_waiting, NULL);
}

template<>
inline void EventSemaphore::CreateImpl(const std::string &id, SharedState *shared_state)
{
    m_LocalState.m_Semaphore = CreateSemaphore(NULL, 0, 9999, (id + ".sem").c_str());

	if (m_LocalState.m_Semaphore == NULL)
		throw std::runtime_error("Something went wrong while creating semaphore.");

	shared_state->m_NumReadersWaiting = 0;
}

template<>
inline void EventSemaphore::OpenImpl(const std::string &id, SharedState *shared_state)
{
    m_LocalState.m_Semaphore = OpenSemaphore(SEMAPHORE_ALL_ACCESS, FALSE, (id + ".sem").c_str());

	if (m_LocalState.m_Semaphore == NULL)
		throw std::runtime_error("Something went wrong while opening semaphore.");
}

template<>
inline EventSemaphore::~EventImpl()
{
    CloseHandle(m_LocalState.m_Semaphore);
}

#ifdef __linux__
#endif // __linux__

#ifdef __APPLE__
#endif // __APPLE__

#endif
