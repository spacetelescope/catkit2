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
	struct Pool
	{
		std::atomic_uint64_t map;
		std::atomic_uint64_t next_and_ref_count;
		std::array<std::atomic_uint16_t, 64> slot_ref_count;

		bool IncrementRefCount();
		bool DecrementRefCount();

		static std::pair<BuddyAllocator::Handle, bool> UnpackNextAndRefCount(std::uint64_t next_and_ref_count);
		static std::uint64_t PackNextAndRefCount(BuddyAllocator::Handle next, std::uint16_t ref_count);
		static std::uint64_t SetNext(std::uint64_t next_and_ref_count, BuddyAllocator::Handle handle);

		static const std::size_t HANDLE_SIZE = 48;
		static const std::size_t REF_COUNT_SIZE = 16;
		static const std::uint64_t HANDLE_MASK = 0xFFFFFFFFFFFF0000;
		static const std::uint64_t REF_COUNT_MASK = 0x7FFF;
		static const std::uint64_t REF_COUNT_FLAG = 0x8000;
	};

public:
	using Handle = BuddyAllocator::Handle;
	static const Handle INVALID_HANDLE = BuddyAllocator::INVALID_HANDLE;

	static std::unique_ptr<HybridPoolAllocator> Create(StructStream &stream, std::size_t capacity, std::size_t min_size, std::size_t min_size_pool);
	static std::unique_ptr<HybridPoolAllocator> Open(StructStream &stream);

	ShareableType GetType() const override;
	static std::size_t GetSharedStateSize(std::size_t capacity, std::size_t min_size);

	Handle Allocate(std::size_t size);
	bool IncrementRefCount(Handle handle);
	bool Deallocate(Handle handle);

private:
	HybridPoolAllocator(std::size_t capacity, std::size_t min_size, std::size_t min_size_pool, std::unique_ptr<BuddyAllocator> allocator, Pool *pools, std::atomic<BuddyAllocator::Handle> *caches);

	std::size_t GetLevel(Handle handle) const;
	void HealCache(std::size_t level);

	std::size_t m_Capacity;
	std::size_t m_MinSize;
	std::size_t m_MinSizePool;

	std::unique_ptr<BuddyAllocator> m_Allocator;

	Pool *m_Pools;

	std::atomic<BuddyAllocator::Handle> *m_Caches;
};

#endif // HYBRID_POOL_ALLOCATOR_H
