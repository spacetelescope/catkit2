#ifndef REF_COUNTER_H
#define REF_COUNTER_H

#include <atomic>
#include <type_traits>

// A wait-free reference counter.
//
// This implementation is based on Daniel Anderson's CppCon 2024 talk.
template<typename T>
class RefCounter
{
	static_assert(std::is_integral_v<T>, "RefCounter can only be used with integral types.");
	static_assert(std::is_unsigned_v<T>, "RefCounter can only be used with unsigned types.");
	static_assert(std::atomic<T>::is_always_lock_free, "RefCounter requires atomic operations to be lock-free.");

private:
	// MSB of the counter indicates whether it's zero or not.
	static constexpr T is_zero = T(1) << (8 * sizeof(T) - 1);

	std::atomic<T> m_Counter;

public:
	inline RefCounter() : m_Counter(1)
	{
	}

	inline bool Increment()
	{
		// Check if the MSB was set before incrementing.
		return (m_Counter.fetch_add(1) & is_zero) == 0;
	}

	inline bool Decrement()
	{
		if (m_Counter.fetch_sub(1) == 1)
		{
			// The counter is now zero. We need to set the MSB to indicate this.
			T e = 0;

			// If we fail, it means that someone else incremented the ref counter before us.
			// Increment linearizes before decrement, so the counter wasn't "actually" zero.
			return m_Counter.compare_exchange_strong(e, is_zero);
		}

		return false;
	}

	inline void Reset()
	{
		m_Counter.store(1, std::memory_order_relaxed);
	}
};

#endif // REF_COUNTER_H
