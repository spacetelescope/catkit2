#include "EventBase.h"

#include "Timing.h"

#include <atomic>
#include <cstddef>
#include <ctime>

#if defined(__linux__) || defined(__APPLE__)
	#include <time.h>
#endif

using EventSpinLockSleep = EventImpl<EventImplementationType::SpinLockSleep>;

// Sleep interval between counter checks (50 microseconds).
const long SLEEP_INTERVAL_NSEC = 50'000;

// Interval between error checks (20 milliseconds).
const double ERROR_CHECK_INTERVAL_SEC = 0.020;

template<>
struct is_event_implemented<EventImplementationType::SpinLockSleep> : std::true_type
{
};

template<>
struct EventSharedState<EventImplementationType::SpinLockSleep>
{
	std::atomic_size_t m_Counter;
};

template<>
inline void EventSpinLockSleep::Wait(double timeout_in_sec, std::function<bool()> condition, void (*error_check)())
{
	Timer timer;

	std::size_t current_counter = m_SharedState->m_Counter.load(std::memory_order_acquire);
	double last_error_check_time = 0.0;

	while (!condition())
	{
		std::size_t new_counter = m_SharedState->m_Counter.load(std::memory_order_acquire);

		if (new_counter != current_counter)
		{
			current_counter = new_counter;
			continue;
		}

		double elapsed = timer.GetTime();

		if (elapsed > timeout_in_sec)
			throw std::runtime_error("Waiting time has expired.");

		if (error_check)
			error_check();

		// Sleep for 50us between counter checks.
		struct timespec ts;
		ts.tv_sec = 0;
		ts.tv_nsec = SLEEP_INTERVAL_NSEC;

		nanosleep(&ts, nullptr);
	}
}

template<>
inline void EventSpinLockSleep::Signal()
{
	m_SharedState->m_Counter.fetch_add(1, std::memory_order_release);
}

template<>
inline void EventSpinLockSleep::CreateImpl(std::string_view id, SharedState *shared_state)
{
	shared_state->m_Counter.store(0);
}

template<>
inline void EventSpinLockSleep::OpenImpl(std::string_view id, SharedState *shared_state)
{
	// Nothing to do.
}
