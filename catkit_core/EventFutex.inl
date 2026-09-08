#include "EventBase.h"

#include "Timing.h"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <chrono>
#include <ctime>
#include <string>

#ifdef __linux__
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif // _GNU_SOURCE
#include <sys/syscall.h>
#include <unistd.h>
#include <linux/futex.h>
#endif // __linux__

using EventFutex = EventImpl<EventImplementationType::Futex>;

#if defined(__linux__) || defined(__APPLE__)

template<>
struct is_event_implemented<EventImplementationType::Futex> : std::true_type
{
};

template<>
struct EventSharedState<EventImplementationType::Futex>
{
	std::atomic<int> m_Futex;
};

// Result of a futex_wait() call, normalized across platforms.
enum class FutexWaitResult
{
	Woken,      // The futex was woken up, or the value did not match the expected value.
	TimedOut,   // The timeout expired.
	Interrupted // The wait was interrupted (e.g. by a signal); check the condition and retry.
};

#ifdef __linux__

inline FutexWaitResult futex_wait(std::atomic<int> *addr, int expected, double timeout_in_sec)
{
	struct timespec timeout;
	timeout.tv_sec = static_cast<time_t>(timeout_in_sec);
	timeout.tv_nsec = 1'000'000'000 * (timeout_in_sec - static_cast<time_t>(timeout_in_sec));

	if (timeout.tv_nsec >= 1'000'000'000)
	{
		timeout.tv_sec += 1;
		timeout.tv_nsec -= 1'000'000'000;
	}

	long res = syscall(SYS_futex, reinterpret_cast<int *>(addr), FUTEX_WAIT, expected, &timeout, nullptr, 0);

	if (res >= 0)
		return FutexWaitResult::Woken;

	switch (errno)
	{
		case EAGAIN:
			// The value was not equal to the expected value. This usually means that
			// the futex was triggered in between us getting the expected value and
			// the futex_wait() call.
			return FutexWaitResult::Woken;
		case ETIMEDOUT:
			return FutexWaitResult::TimedOut;
		case EINTR:
			return FutexWaitResult::Interrupted;
		default:
			throw std::runtime_error("Futex wait failed: " + std::to_string(errno));
	}
}

inline void futex_wake(std::atomic<int> *addr)
{
	if (syscall(SYS_futex, reinterpret_cast<int *>(addr), FUTEX_WAKE, INT32_MAX, nullptr, nullptr, 0) < 0)
	{
		throw std::runtime_error("Futex wake failed: " + std::to_string(errno));
	}
}

#endif // __linux__

#ifdef __APPLE__

// macOS has no public futex API before macOS 14.4 (os_sync_wait_on_address). We use the
// underlying __ulock_wait/__ulock_wake system calls directly, which have been stable since
// macOS 10.12 and are used by libc++, libdispatch and others. The *_SHARED variant, which is
// required for memory shared between processes, is available since macOS 10.15.
//
// Note that we cannot use process-shared pthread condition variables for this purpose on macOS:
// Apple's libpthread stores the address of the mutex used by the first waiter inside the
// condition variable, and rejects (with EINVAL, without releasing the mutex) any waiter that
// uses the same mutex mapped at a different virtual address, which is the case for every other
// process that maps the same shared memory.
extern "C" int __ulock_wait(uint32_t operation, void *addr, uint64_t value, uint32_t timeout_us);
extern "C" int __ulock_wake(uint32_t operation, void *addr, uint64_t wake_value);

const uint32_t CATKIT_UL_COMPARE_AND_WAIT_SHARED = 3;
const uint32_t CATKIT_ULF_WAKE_ALL = 0x00000100;
const uint32_t CATKIT_ULF_NO_ERRNO = 0x01000000;

inline FutexWaitResult futex_wait(std::atomic<int> *addr, int expected, double timeout_in_sec)
{
	// A timeout of zero means to wait indefinitely, so make sure we wait at least 1us.
	uint32_t timeout_us = static_cast<uint32_t>(timeout_in_sec * 1'000'000);
	if (timeout_us == 0)
		timeout_us = 1;

	int res = __ulock_wait(CATKIT_UL_COMPARE_AND_WAIT_SHARED | CATKIT_ULF_NO_ERRNO, reinterpret_cast<void *>(addr), static_cast<uint64_t>(static_cast<uint32_t>(expected)), timeout_us);

	// A non-negative return value means we were woken up, or the value did not match
	// the expected value in the first place.
	if (res >= 0)
		return FutexWaitResult::Woken;

	switch (-res)
	{
		case ETIMEDOUT:
			return FutexWaitResult::TimedOut;
		case EINTR:
		case EFAULT:
			// EFAULT can be returned if the page is not resident (e.g. right after mapping).
			// In both cases, simply check the condition again and retry.
			return FutexWaitResult::Interrupted;
		default:
			throw std::runtime_error("Futex wait failed: " + std::to_string(-res));
	}
}

inline void futex_wake(std::atomic<int> *addr)
{
	int res = __ulock_wake(CATKIT_UL_COMPARE_AND_WAIT_SHARED | CATKIT_ULF_WAKE_ALL | CATKIT_ULF_NO_ERRNO, reinterpret_cast<void *>(addr), 0);

	// ENOENT means that there were no waiters, which is not an error.
	if (res < 0 && -res != ENOENT)
	{
		throw std::runtime_error("Futex wake failed: " + std::to_string(-res));
	}
}

#endif // __APPLE__

template<>
inline void EventFutex::Wait(double timeout_in_sec, std::function<bool()> condition, void (*error_check)())
{
	Timer timer;

	while (true)
	{
		// Read the expected value *before* checking the condition. If the event is signaled
		// in between the condition check and the futex_wait() call, the futex value will no
		// longer match and futex_wait() returns immediately, so no wakeup can be lost.
		int expected = m_SharedState->m_Futex.load(std::memory_order_acquire);

		if (condition())
			return;

		// Wait for a maximum of 20ms to perform periodic error checking.
		double time_remaining = timeout_in_sec - timer.GetTime();
		double timeout_wait = std::min(0.020, time_remaining);

		if (timeout_wait <= 0)
		{
			// The timeout expired.
			throw std::runtime_error("Waiting time has expired.");
		}

		// The result is not used: regardless of whether we were woken up, timed out or
		// were interrupted, we perform the error check and re-check the condition.
		futex_wait(&m_SharedState->m_Futex, expected, timeout_wait);

		if (error_check != nullptr)
			error_check();
	}
}

template<>
inline void EventFutex::Signal()
{
	m_SharedState->m_Futex.fetch_add(1, std::memory_order_release);

	futex_wake(&m_SharedState->m_Futex);
}

template<>
inline void EventFutex::CreateImpl(std::string_view id, SharedState *shared_state)
{
	shared_state->m_Futex = 0;
}

#endif // defined(__linux__) || defined(__APPLE__)
