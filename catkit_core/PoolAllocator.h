#ifndef POOL_ALLOCATOR_H
#define POOL_ALLOCATOR_H

#include <atomic>
#include <cstdint>
#include <cstddef>
#include <limits>
#include <memory>

// A simple lock-free pool allocator.
class PoolAllocator
{
public:
	using BlockHandle = std::uint32_t;
	static const BlockHandle INVALID_HANDLE = std::numeric_limits<BlockHandle>::max();

	static std::size_t CalculateMetadataBufferSize(std::uint32_t capacity);

	static std::shared_ptr<PoolAllocator> Create(void *metadata_buffer, std::uint32_t capacity);
	static std::shared_ptr<PoolAllocator> Open(void *metadata_buffer);

	BlockHandle Allocate();
	void Deallocate(BlockHandle index);

private:
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

	PoolAllocator(Header *header, std::atomic<BlockHandle> *next);

	static void GetMemoryLayout(void *metadata_buffer, std::atomic<BlockHandle> **next);

	Header &m_Header;

	std::uint32_t &m_Capacity;
	std::atomic<BlockHandle> &m_Head;
	std::atomic<BlockHandle> *m_Next;
};

#endif // POOL_ALLOCATOR_H
