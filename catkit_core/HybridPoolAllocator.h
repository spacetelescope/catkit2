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

	struct HandleAndRefCount
	{
		std::atomic_uint64_t m_HandleAndRefCount;

		std::pair<BuddyAllocator::Handle, bool> Get() const;

		const std::uint64_t HANDLE_MASK = 0xFFFFFFFFFFFF0000;
		const std::uint64_t REF_COUNT_MASK = 0x7FFF;
		const std::uint64_t REF_COUNT_FLAG = 0x8000;
	};

	struct Pool
	{
		std::atomic_uint64_t map;
		std::atomic<HandleAndRefCount> next_and_ref_count;
		std::array<std::uint16_t, 64> slot_ref_count;

		bool IncrementRefCount();
		bool DecrementRefCount();
	};

	using Handle = BuddyAllocator::Handle;
	const Handle INVALID_HANDLE = BuddyAllocator::INVALID_HANDLE;

	HybridPoolAllocator(std::size_t capacity, std::size_t min_size, std::size_t min_size_pool, std::unique_ptr<BuddyAllocator> allocator, Pool *pools, std::atomic<HandleAndRefCount> *caches);

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

	Pool *m_Pools;

	std::atomic<HandleAndRefCount> *m_Caches;
};

#endif // HYBRID_POOL_ALLOCATOR_H
