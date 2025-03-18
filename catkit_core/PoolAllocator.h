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
class PoolAllocator : public Shareable
{
public:
	using BlockHandle = std::uint32_t;
	static const BlockHandle INVALID_HANDLE = std::numeric_limits<BlockHandle>::max();

	static std::size_t GetSharedStateSize(std::uint32_t capacity);

	static std::unique_ptr<PoolAllocator> Create(StructStream &stream, std::uint32_t capacity);
	static std::unique_ptr<PoolAllocator> Open(StructStream &stream);

	BlockHandle Allocate();
	void IncrementRefCount(BlockHandle index);
	void Deallocate(BlockHandle index);

	ShareableType GetType() const override;

private:
	PoolAllocator(std::uint32_t capacity, std::atomic<BlockHandle> *head, std::atomic<BlockHandle> *next, std::atomic_size_t *ref_count);

	std::uint32_t m_Capacity;
	std::atomic<BlockHandle> *m_Head;
	std::atomic<BlockHandle> *m_Next;
	std::atomic_size_t *m_RefCount;

	static_assert(std::atomic<BlockHandle>::is_always_lock_free);
};

#endif // POOL_ALLOCATOR_H
