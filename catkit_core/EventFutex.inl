#include "EventBase.h"

#include <atomic>
#include <chrono>
#include <ctime>

#ifdef __linux__
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif // _GNU_SOURCE
#include <sys/syscall.h>
#include <unistd.h>
#include <linux/futex.h>
#endif // __linux__

using EventFutex = EventImpl<EventImplementationType::Futex>;

#ifdef __linux__

template<>
struct EventSharedState<EventImplementationType::Futex>
{
	std::atomic<int> m_Futex;
};

inline int futex_wait(std::atomic<int> *addr, int expected, const struct timespec* timeout)
{
	return syscall(SYS_futex, reinterpret_cast<int *>(addr), FUTEX_WAIT, expected, timeout, nullptr, 0);
}

inline int futex_wake(std::atomic<int> *addr, int count)
{
	return syscall(SYS_futex, reinterpret_cast<int *>(addr), FUTEX_WAKE, count, nullptr, nullptr, 0);
}

template<>
inline void EventFutex::Wait(double timeout_in_sec, std::function<bool()> condition, void (*error_check)())
{
	Timer timer;
	int expected = m_SharedState->m_Futex.load(std::memory_order_acquire);

	while (!condition())
	{
		// Wait for a maximum of 20ms to perform periodic error checking.
		double time_remaining = timeout_in_sec - timer.GetTime();
		double timeout_wait = std::min(0.020, timeout_in_sec);

		struct timespec timeout;
		clock_gettime(CLOCK_MONOTONIC, &timeout);
		timeout.tv_sec += static_cast<time_t>(timeout_wait);
		timeout.tv_nsec += 1'000'000'000 * (timeout_wait - static_cast<time_t>(timeout_wait));

		if (futex_wait(&m_SharedState->m_Futex, expected, &timeout) < 0)
		{
			if (errno == EAGAIN)
			{
				// The value was not equal to the expected value, so we need to check the condition again.
				expected = m_SharedState->m_Futex.load(std::memory_order_acquire);
				continue;
			}

			// Otherwise, an error occurred.
			throw std::runtime_error("Futex wait failed.");
		}

		if (error_check != nullptr)
			error_check();
	}
}

template<>
inline void EventFutex::Signal()
{
	m_SharedState->m_Futex.fetch_add(1, std::memory_order_release);

	if (futex_wake(&m_SharedState->m_Futex, INT32_MAX) < 0)
	{
		throw std::runtime_error("Futex wake failed.");
	}
}

template<>
inline void EventFutex::CreateImpl(std::string_view id, SharedState *shared_state)
{
	shared_state->m_Futex = 0;
}

#endif // __linux__
