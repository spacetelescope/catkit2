#ifndef POOL_ALLOCATOR_H
#define POOL_ALLOCATOR_H

#include <atomic>
#include <cstdint>

// A simple lock-free pool allocator.
template<std::size_t Size>
class PoolAllocator
{
private:
	std::atomic_size_t m_Head;
	std::atomic_size_t m_Next[Size];
public:
	PoolAllocator()
		: m_Head(0);
	{
		// Initialize the linked list.
		for (size_t i = 0; i < Size; ++i)
		{
			if (i == Size - 1)
			{
				m_Next[i] = -1;
			}
			else
			{
				m_Next[i] = i + 1;
			}
		}
	}

	size_t Allocate()
	{
		std::size_t head;
		std::size_t next;

		// Pop the first element from the linked list.
		do
		{
			head = m_Head.load(std::memory_order_relaxed);

			// Check if the pool is empty.
			if (head == -1)
			{
				return nullptr;
			}

			next = m_Next[head].load(std::memory_order_relaxed);
		} while (!m_Head.compare_exchange_weak(head, next));

		// Return the popped element.
		return head;
	}

	void Deallocate(size_t index)
	{
		// Check if the element is within the pool bounds.
		if (index >= Size)
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
