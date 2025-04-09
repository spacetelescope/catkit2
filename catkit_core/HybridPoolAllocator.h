#ifndef HYBRID_POOL_ALLOCATOR_H
#define HYBRID_POOL_ALLOCATOR_H

#include "BuddyAllocator.h"
#include "PoolAllocator.h"
#include "Shareable.h"
#include "RefCounter.h"

#include <cstddef>
#include <cstdint>
#include <atomic>

class HybridPoolAllocator : public Shareable
{
private:

	class MarkedHandle
	{
	public:
		MarkedHandle();
		MarkedHandle(BuddyAllocator::Handle handle);

		BuddyAllocator::Handle GetHandle() const;
		void SetHandle(const BuddyAllocator::Handle &handle);

		bool IsMarked() const;
		void Mark();

	private:
		BuddyAllocator::Handle m_HandleAndMark;
	};

	struct Block
	{
		std::atomic_uint64_t map;
		std::atomic<MarkedHandle> next;
		RefCounter<std::uint64_t> ref_count;
		std::array<std::uint16_t, 64> sub_ref_count;
	};

	using Handle = BuddyAllocator::Handle;
	const Handle INVALID_HANDLE = BuddyAllocator::INVALID_HANDLE;

	HybridPoolAllocator(std::size_t capacity, std::size_t min_size, std::size_t min_size_pool, std::unique_ptr<BuddyAllocator> allocator, Block *blocks, std::atomic<MarkedHandle> *caches);

public:
	static std::unique_ptr<HybridPoolAllocator> Create(StructStream &stream, std::size_t capacity, std::size_t min_size, std::size_t min_size_pool);
	static std::unique_ptr<HybridPoolAllocator> Open(StructStream &stream);

	ShareableType GetType() const override;
	static std::size_t GetSharedStateSize(std::size_t capacity, std::size_t min_size);

	Handle Allocate(std::size_t size);
	bool IncrementRefCount(Handle handle);
	bool Deallocate(Handle handle);

private:
	std::size_t GetLevel(Handle handle);

	void AllocatePool(std::size_t level);
	void DeallocatePool(BuddyAllocator::Handle handle);

	std::size_t m_Capacity;
	std::size_t m_MinSize;
	std::size_t m_MinSizePool;

	std::unique_ptr<BuddyAllocator> m_Allocator;

	Block *m_Blocks;

	std::atomic<MarkedHandle> *m_Caches;
};

#endif // HYBRID_POOL_ALLOCATOR_H
