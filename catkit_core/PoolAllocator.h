#ifndef POOL_ALLOCATOR_H
#define POOL_ALLOCATOR_H

 #include "Shareable.h"

#include <atomic>
#include <cstdint>
#include <cstddef>
#include <limits>
#include <memory>
#include <array>

// A simple lock-free pool allocator.
class PoolAllocator
{
public:
	using BlockHandle = std::uint32_t;
	static const BlockHandle INVALID_HANDLE = std::numeric_limits<BlockHandle>::max();

	static std::size_t GetMemorySize(std::uint32_t capacity);

	static std::unique_ptr<PoolAllocator> Create(StructStream &stream, std::uint32_t capacity);
	static std::unique_ptr<PoolAllocator> Open(StructStream &stream);

	BlockHandle Allocate();
	void Deallocate(BlockHandle index);

private:
	PoolAllocator(StructStream &stream, std::uint32_t capacity);

	std::array<std::uint8_t, 4> *m_Version;
	std::uint32_t *m_Capacity;
	std::atomic<BlockHandle> *m_Head;
	std::atomic<BlockHandle> *m_Next;

	static_assert(std::atomic<BlockHandle>::is_always_lock_free);
};

#endif // POOL_ALLOCATOR_H
