#ifndef POOL_ALLOCATOR_H
#define POOL_ALLOCATOR_H

#include <atomic>
#include <cstdint>

// A simple lock-free pool allocator.
template<typename Value, std::int32_t Size>
class PoolAllocator
{
private:
	Value m_Pool[Size];

	std::atomic_int32_t m_Head;
	std::atomic_int32_t m_Next[Size];
public:
	PoolAllocator()
		: m_Head(0);
	{
		// Check that size is smaller than maximum value of int32_t - 1.
		static_assert(Size < INT32_MAX - 1, "Size must be smaller than INT32_MAX - 1.");

		// Initialize the linked list.
		for (size_t i = 0; i < Size; ++i)
		{
			m_Next[i] = i + 1;
		}
	}

	Value *Allocate()
	{
		std::int32_t head;
		std::int32_t next;

		// Pop the first element from the linked list.
		do
		{
			head = m_Head.load(std::memory_order_relaxed);
			next = m_Next[head].load(std::memory_order_relaxed);
		} while (!m_Head.compare_exchange_weak(head, next));

		// Return the popped element.
		return &m_Pool[head];
	}

	void Deallocate(Value *element)
	{
		// Ignore null pointers.
		if (element == nullptr)
		{
			return;
		}

		// Check that the element is within the pool.
		std::int32_t index = element - m_Pool;

		if (index < 0 || index >= Size)
		{
			return;
		}

		// Push the element back on the front of the linked list.
		do
		{
			m_Next[index] = m_Head.load(std::memory_order_relaxed);
		} while (!m_Head.compare_exchange_weak(m_Next[index], index));
	}
};

#endif // POOL_ALLOCATOR_H
