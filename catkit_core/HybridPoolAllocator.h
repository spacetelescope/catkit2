#ifndef HYBRID_POOL_ALLOCATOR_H
#define HYBRID_POOL_ALLOCATOR_H

#include "BuddyAllocator.h"
#include "PoolAllocator.h"
#include "Shareable.h"
#include "ConcurrentVector.h"
#include "RefCounter.h"

#include <cstddef>
#include <cstdint>
#include <atomic>
#include <vector>
#include <list>
#include <mutex>
#include <array>

class HybridPoolAllocator : public Shareable
{
private:
	struct Pool
	{
		std::uint64_t map;
		std::array<RefCounter<std::uint16_t>, 64> ref_counts;
	};

public:
	using Handle = BuddyAllocator::Handle;
	static const Handle INVALID_HANDLE = BuddyAllocator::INVALID_HANDLE;

	static std::shared_ptr<HybridPoolAllocator> Create(StructStream &stream, std::size_t capacity, std::size_t min_size, std::size_t min_size_pool);
	static std::shared_ptr<HybridPoolAllocator> Open(StructStream &stream);

	ShareableType GetType() const override;
	static std::size_t GetSharedStateSize(std::size_t capacity, std::size_t min_size);

	Handle Allocate(std::size_t size);
	bool Acquire(Handle handle);
	bool Release(Handle handle);

	std::size_t GetOffset(Handle handle) const;

public:
	HybridPoolAllocator(std::size_t capacity, std::size_t min_size, std::size_t min_size_pool, std::shared_ptr<BuddyAllocator> allocator, Pool *pools);

	std::size_t GetLevelFromHandle(Handle handle) const;
	std::size_t GetLevelFromSize(std::size_t size) const;
	std::size_t GetSizeFromHandle(Handle handle) const;

	std::size_t m_Capacity;
	std::size_t m_MinSize;
	std::size_t m_MinSizePool;

	std::shared_ptr<BuddyAllocator> m_Allocator;

	Pool *m_Pools;

	using Bucket = std::vector<BuddyAllocator::Handle>;
	static constexpr std::size_t MAX_NUM_LEVELS = 64;

	// An array of buckets for each thread.
	ConcurrentVector<std::array<Bucket, MAX_NUM_LEVELS>> m_Buckets;

	Bucket &GetBucket(std::size_t level);
};

#endif // HYBRID_POOL_ALLOCATOR_LOCAL_H
