#include "EventBase.h"

#include <atomic>
#include <cstddef>
#include <thread>

using EventSpinLock = EventImpl<EventImplementationType::SpinLock>;

const std::size_t NUM_ITERATIONS_BETWEEN_CHECKS = 16;

template<>
struct is_event_implemented<EventImplementationType::SpinLock> : std::true_type
{
};

template<>
struct EventSharedState<EventImplementationType::SpinLock>
{
	std::atomic_size_t m_Counter;
};

template<>
inline void EventSpinLock::Wait(double timeout_in_sec, std::function<bool()> condition, void (*error_check)())
{
	Timer timer;

	std::size_t current_counter = m_SharedState->m_Counter.load(std::memory_order_acquire);
	std::size_t i = 0;

	while (!condition())
	{
		while (true)
		{
			std::size_t new_counter = m_SharedState->m_Counter.load(std::memory_order_acquire);

			if (new_counter != current_counter)
			{
				current_counter = new_counter;
				break;
			}

			if (++i == NUM_ITERATIONS_BETWEEN_CHECKS)
			{
				// If we've been waiting for a long time, then the lock is probably deadlocked.
				if (error_check != nullptr)
					error_check();

				if (timer.GetTime() > timeout_in_sec)
					throw std::runtime_error("Waiting time has expired.");

				i = 0;

				// Yield the thread to allow other threads to run.
				std::this_thread::yield();
			}
		}
	}
}

template<>
inline void EventSpinLock::Signal()
{
	m_SharedState->m_Counter.fetch_add(1, std::memory_order_release);
}

template<>
inline void EventSpinLock::CreateImpl(std::string_view id, SharedState *shared_state)
{
	shared_state->m_Counter.store(0);
}
