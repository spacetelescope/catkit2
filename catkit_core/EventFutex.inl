#include "EventBase.h"

#include <algorithm>
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

#if defined(__APPLE__)
#include <cerrno>
#include <os/os_sync_wait_on_address.h>
#endif // defined(__APPLE__)

using EventFutex = EventImpl<EventImplementationType::Futex>;

#ifdef __linux__

template<>
struct is_event_implemented<EventImplementationType::Futex> : std::true_type
{
};

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
		double timeout_wait = std::min(0.020, time_remaining);

		if (timeout_wait <= 0)
		{
			// The timeout expired.
			throw std::runtime_error("Waiting time has expired.");
		}

		struct timespec timeout;
		timeout.tv_sec = static_cast<time_t>(timeout_wait);
		timeout.tv_nsec = 1'000'000'000 * (timeout_wait - static_cast<time_t>(timeout_wait));

		if (timeout.tv_nsec >= 1'000'000'000)
		{
			timeout.tv_sec += 1;
			timeout.tv_nsec -= 1'000'000'000;
		}

		if (futex_wait(&m_SharedState->m_Futex, expected, &timeout) < 0)
		{
			if (errno == EAGAIN)
			{
				// The value was not equal to the expected value. This usually means that
				// the futex was triggered in between us getting the expected value and
				// the futex_wait() call. So we need to reset the expected value and check
				// the condition before calling futex_wait() again.
				expected = m_SharedState->m_Futex.load(std::memory_order_acquire);
				continue;
			}

			if (errno == ETIMEDOUT)
			{
				// The futex timed out. We should check the condition and futex_wait() again.
				continue;
			}

			// Otherwise, an error occurred.
			throw std::runtime_error("Futex wait failed: " + std::to_string(errno));
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

#if defined(__APPLE__)

template<>
struct is_event_implemented<EventImplementationType::Futex> : std::true_type
{
};

template<>
struct EventSharedState<EventImplementationType::Futex>
{
	std::atomic<uint32_t> m_Futex;
};

template<>
inline void EventFutex::Wait(double timeout_in_sec, std::function<bool()> condition, void (*error_check)())
{
	Timer timer;
	uint64_t expected = m_SharedState->m_Futex.load(std::memory_order_acquire);

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

		// A timeout of 0 results in EINVAL, so clamp it to 1ns.
		uint64_t timeout_ns = std::max(1ULL, static_cast<uint64_t>(timeout_wait * 1'000'000'000.0));

		// The futex value lives in a shared memory region, so the SHARED flag
		// must be used consistently on both the wait and wake sides for waiters
		// to be found and woken (including across processes).
		int res = os_sync_wait_on_address_with_timeout(
			reinterpret_cast<void *>(&m_SharedState->m_Futex),
			expected,
			sizeof(uint32_t),
			OS_SYNC_WAIT_ON_ADDRESS_SHARED,
			OS_CLOCK_MACH_ABSOLUTE_TIME,
			timeout_ns);

		if (res < 0)
		{
			if (errno == ETIMEDOUT)
			{
				// The wait timed out. Run the error check (e.g. to detect Python
				// KeyboardInterrupts) periodically, then check the condition and
				// wait again.
				if (error_check != nullptr)
					error_check();

				continue;
			}

			if (errno == EINTR || errno == EFAULT || errno == ENOMEM)
			{
				// The wait was interrupted or failed transiently (e.g. low memory
				// conditions). Refresh the expected value and wait again, as
				// recommended by the API.
				expected = m_SharedState->m_Futex.load(std::memory_order_acquire);
				continue;
			}

			// Otherwise, an error occurred.
			throw std::runtime_error("Futex wait failed: " + std::to_string(errno));
		}

		// The futex was woken or the value changed. Update the expected value
		// before waiting again.
		expected = m_SharedState->m_Futex.load(std::memory_order_acquire);

		if (error_check != nullptr)
			error_check();
	}
}

template<>
inline void EventFutex::Signal()
{
	m_SharedState->m_Futex.fetch_add(1, std::memory_order_release);

	// The futex value lives in a shared memory region, so the SHARED flag must
	// be used consistently on both the wait and wake sides for waiters to be
	// found and woken (including across processes).
	int res = os_sync_wake_by_address_all(
		reinterpret_cast<void *>(&m_SharedState->m_Futex),
		sizeof(uint32_t),
		OS_SYNC_WAKE_BY_ADDRESS_SHARED);
	int err = errno;

	// ENOENT means there are no waiters to wake, which is a valid outcome (e.g.
	// the event is signaled while nobody is blocked on the futex). EINTR, ENOMEM
	// and EFAULT are transient conditions; the futex value was already
	// incremented, so any waiter will observe the change and not block. Only
	// other errors indicate a real failure.
	if (res < 0 && err != ENOENT && err != EINTR && err != ENOMEM && err != EFAULT)
	{
		throw std::runtime_error("Futex wake failed: " + std::to_string(err));
	}
}

template<>
inline void EventFutex::CreateImpl(std::string_view id, SharedState *shared_state)
{
	shared_state->m_Futex.store(0);
}

#endif // defined(__APPLE__)
