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
class PoolAllocator : public ShareableImpl<ShareableType::PoolAllocator>
{
public:
	using BlockHandle = std::uint32_t;
	static const BlockHandle INVALID_HANDLE = std::numeric_limits<BlockHandle>::max();

	static std::size_t CalculateMetadataBufferSize(std::uint32_t capacity);

	static std::unique_ptr<PoolAllocator> Create(SharedState *shared_state, std::uint32_t capacity);
	static std::unique_ptr<PoolAllocator> Open(SharedState *shared_state);

	BlockHandle Allocate();
	void Deallocate(BlockHandle index);

	struct Header
	{
		std::uint8_t version[4];
		std::uint32_t capacity;
		std::atomic<BlockHandle> head;
	};

	// Ensure a specific memory layout.
	static_assert(offsetof(PoolAllocator::Header, version) == 0);
	static_assert(offsetof(PoolAllocator::Header, capacity) == 4);
	static_assert(offsetof(PoolAllocator::Header, head) == 8);
	static_assert(sizeof(PoolAllocator::Header) == 12);

private:
	PoolAllocator(SharedState *header, std::atomic<BlockHandle> *next);

	static void GetMemoryLayout(SharedState *shared_state, std::atomic<BlockHandle> **next);

	Header &m_Header;

	std::uint32_t &m_Capacity;
	std::atomic<BlockHandle> &m_Head;
	std::atomic<BlockHandle> *m_Next;
};

template<>
struct SharedStateInternal<ShareableType::PoolAllocator>
{
	PoolAllocator::Header header;
};

#endif // POOL_ALLOCATOR_H
