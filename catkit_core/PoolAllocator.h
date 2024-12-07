#ifndef POOL_ALLOCATOR_H
#define POOL_ALLOCATOR_H

#include <atomic>
#include <cstdint>
#include <cstddef>

// A simple lock-free pool allocator.
class PoolAllocator
{
public:
	PoolAllocator(void *buffer, size_t capacity);

	void Initialize();

	static std::size_t CalculateBufferSize(std::size_t capacity);

	size_t Allocate();
	void Deallocate(size_t index);

private:
	std::size_t m_Capacity;
	std::atomic_size_t *m_Head;
	std::atomic_size_t *m_Next;
};

#endif // POOL_ALLOCATOR_H
