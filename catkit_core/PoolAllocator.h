#ifndef POOL_ALLOCATOR_H
#define POOL_ALLOCATOR_H

#include <atomic>
#include <cstdint>
#include <cstddef>

// A simple lock-free pool allocator.
template<std::size_t Size>
class PoolAllocator
{
private:
	std::atomic_size_t m_Head;
	std::atomic_size_t m_Next[Size];
public:
	PoolAllocator();

	size_t Allocate();
	void Deallocate(size_t index);
};

#include "PoolAllocator.inl"

#endif // POOL_ALLOCATOR_H
