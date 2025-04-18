#include "HybridPoolAllocator.h"
#include "Util.h"

#include <array>
#include <stdexcept>

const std::array<std::uint8_t, 4> HYBRID_POOL_ALLOCATOR_VERSION = {0, 0, 0, 0};

HybridPoolAllocator::HybridPoolAllocator(std::size_t capacity, std::size_t min_size, std::size_t min_size_pool, std::unique_ptr<BuddyAllocator> allocator, Pool *pools)
	: m_Capacity(capacity), m_MinSize(min_size), m_MinSizePool(min_size_pool), m_Allocator(std::move(allocator)), m_Pools(pools)
{
}

std::unique_ptr<HybridPoolAllocator> HybridPoolAllocator::Create(StructStream &stream, std::size_t capacity, std::size_t min_size, std::size_t min_size_pool)
{
	*stream.Extract<std::array<std::uint8_t, 4>>() = HYBRID_POOL_ALLOCATOR_VERSION;

	*stream.Extract<std::size_t>() = capacity;
	*stream.Extract<std::size_t>() = min_size;
	*stream.Extract<std::size_t>() = min_size_pool;

	auto allocator_min_size = std::min(min_size_pool, 64 * min_size);

	std::unique_ptr<BuddyAllocator> allocator = BuddyAllocator::Create(stream, capacity, allocator_min_size);

	auto buddy_allocator_depth = bit_width(capacity / allocator_min_size) - 1;
	auto buddy_allocator_num_blocks = 1ull << (buddy_allocator_depth + 1);

	Pool *pools = stream.Extract<Pool>(buddy_allocator_num_blocks);

	for (std::size_t i = 0; i < buddy_allocator_num_blocks; ++i)
		pools[i].map = 0;

	return std::unique_ptr<HybridPoolAllocator>(new HybridPoolAllocator(capacity, min_size, min_size_pool, std::move(allocator), pools));
}

std::unique_ptr<HybridPoolAllocator> HybridPoolAllocator::Open(StructStream &stream)
{
	CheckVersion(stream, HYBRID_POOL_ALLOCATOR_VERSION);

	auto capacity = *stream.Extract<std::size_t>();
	auto min_size = *stream.Extract<std::size_t>();
	auto min_size_pool = *stream.Extract<std::size_t>();

	auto allocator_min_size = std::min(min_size_pool, 64 * min_size);

	auto allocator = BuddyAllocator::Open(stream);

	auto buddy_allocator_depth = bit_width(capacity / allocator_min_size) - 1;
	auto buddy_allocator_num_blocks = 1ull << (buddy_allocator_depth + 1);

	auto pools = stream.Extract<Pool>(buddy_allocator_num_blocks);

	return std::unique_ptr<HybridPoolAllocator>(new HybridPoolAllocator(capacity, min_size, min_size_pool, std::move(allocator), pools));
}

ShareableType HybridPoolAllocator::GetType() const
{
	return ShareableType::HybridPoolAllocator;
}

std::size_t HybridPoolAllocator::GetSharedStateSize(std::size_t capacity, std::size_t min_size)
{
	return 1024 * 1024 * 1024;
}

HybridPoolAllocator::Handle HybridPoolAllocator::Allocate(std::size_t size)
{
	size = round_up_to_power_of_2(size);

	if (size < m_MinSize)
		size = m_MinSize;

	if (size >= m_MinSizePool)
	{
		// The size is too large to use pools. Defer to the buddy allocator.
		return m_Allocator->Allocate(size);
	}

	std::size_t level = GetLevelFromSize(size);
	Bucket &bucket = GetBucket(level);

	// Loop over the pools in the bucket and find a pool with an available slot.
	for (auto it = bucket.rbegin(); it < bucket.rend(); ++it)
	{
		Handle handle = *it;
		Pool &pool = m_Pools[handle];

		auto val_inv = ~(pool.map);

		if (val_inv == 0)
		{
			// No slots available in this pool. Move to the next.
			continue;
		}

		Handle sub_handle = bit_width(val_inv) - 1;
		auto mask = (1ull << sub_handle);

		pool.map |= mask;

		if (~(pool.map) == 0)
		{
			// The pool is full. Remove it from the bucket.
			bucket.erase(std::next(it).base());
		}

		// Set the reference count.
		pool.ref_counts[sub_handle].Reset();

		return (handle << 6) + sub_handle;
	}

	// No slot in any pool was available. Allocate a new pool.
	auto new_handle = m_Allocator->Allocate(size * 64);

	if (new_handle == BuddyAllocator::INVALID_HANDLE)
	{
		throw std::runtime_error("Failed to allocate a new pool.");
	}

	Pool &pool = m_Pools[new_handle];

	bucket.emplace_back(new_handle);

	// Set the map and reset the reference count of this slot.
	pool.map = 1;
	pool.ref_counts[0].Reset();

	return new_handle << 6;
}

bool HybridPoolAllocator::Acquire(Handle handle)
{
	// Get the level of this block.
	std::size_t level = GetLevelFromHandle(handle);

	// Get the size of blocks at this level.
	std::size_t size = m_Capacity >> level;

	if (size >= m_MinSizePool)
	{
		// This is a block in the allocator.
		return m_Allocator->IncrementRefCount(handle);
	}
	else
	{
		// This is a block in one of our pools. Find cache handle and sub handle.
		BuddyAllocator::Handle pool_handle = handle >> 6;
		Handle sub_handle = (handle & ((1 << 6) - 1));
		std::uint64_t mask = 1ull << sub_handle;

		Pool &pool = m_Pools[pool_handle];

		return pool.ref_counts[sub_handle].Increment();
	}
}

bool HybridPoolAllocator::Release(Handle handle)
{
	// Get the level of this block.
	std::size_t level = GetLevelFromHandle(handle);

	// Get the size of blocks at this level.
	std::size_t size = m_Capacity >> level;

	if (size >= m_MinSizePool)
	{
		// This is a block in the allocator.
		return m_Allocator->Deallocate(handle);
	}
	else
	{
		// This is a block in one of our pools. Find cache handle and sub handle.
		BuddyAllocator::Handle pool_handle = handle >> 6;
		Handle sub_handle = (handle & ((1 << 6) - 1));
		std::uint64_t mask = 1ull << sub_handle;

		Pool &pool = m_Pools[pool_handle];

		if (!pool.ref_counts[sub_handle].Decrement())
		{
			// Someone else is still owning this slot. Return.
			return false;
		}

		auto &bucket = GetBucket(level);

		// Add the pool on the bucket if it's not entirely full anymore after
		// we free the slot.
		if (~(pool.map) == 0)
		{
			bucket.emplace_back(pool_handle);
		}

		// Update the pool bitmap.
		pool.map &= ~mask;

		if (pool.map == 0)
		{
			// The pool is now empty.
			m_Allocator->Deallocate(pool_handle);

			// Find the pool in the bucket.
			auto it = std::find(bucket.begin(), bucket.end(), pool_handle);
			bucket.erase(it);
		}

		return true;
	}
}

std::size_t HybridPoolAllocator::GetLevelFromHandle(Handle handle) const
{
	return bit_width(handle) - 1;
}

std::size_t HybridPoolAllocator::GetLevelFromSize(std::size_t size) const
{
	return GetLevelFromHandle(m_Capacity / size);
}

HybridPoolAllocator::Bucket &HybridPoolAllocator::GetBucket(std::size_t level)
{
	auto thread_id = GetThreadId();

	while (thread_id >= m_Buckets.Size())
	{
		m_Buckets.PushBack({});
	}

	return m_Buckets[thread_id][level];
}
