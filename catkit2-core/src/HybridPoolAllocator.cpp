#include "HybridPoolAllocator.h"
#include "Util.h"

#include <array>
#include <stdexcept>
#include <iostream>

//#define DEBUG_PRINT(a) std::cout << a << std::endl
#define DEBUG_PRINT(a)

const std::array<std::uint8_t, 4> HYBRID_POOL_ALLOCATOR_VERSION = {0, 0, 0, 0};

HybridPoolAllocator::HybridPoolAllocator(std::size_t capacity, std::size_t min_size, std::size_t min_size_pool, std::shared_ptr<BuddyAllocator> allocator, Pool *pools, std::shared_ptr<Memory> memory_block)
	: Shareable(memory_block), m_Capacity(capacity), m_MinSize(min_size), m_MinSizePool(min_size_pool), m_Allocator(std::move(allocator)), m_Pools(pools)
{
}

HybridPoolAllocator::~HybridPoolAllocator()
{
	// Release all pools.
	// The pools will be deallocated when all slots are released.
	for (size_t i = 0; i < m_Buckets.Size(); ++i)
	{
		auto &buckets = m_Buckets[i];

		for (auto &bucket : buckets)
		{
			for (auto &pool : bucket)
			{
				DEBUG_PRINT("Releasing pool " << pool);

				m_Allocator->Release(pool);
			}
			DEBUG_PRINT("Done with bucket.");
		}
		DEBUG_PRINT("Done with buckets for this thread.");
	}
	DEBUG_PRINT("Done with all buckets.");
}

std::shared_ptr<HybridPoolAllocator> HybridPoolAllocator::Create(StructStream &stream, std::size_t capacity, std::size_t min_size, std::size_t min_size_pool)
{
	*stream.Extract<std::array<std::uint8_t, 4>>() = HYBRID_POOL_ALLOCATOR_VERSION;

	*stream.Extract<std::size_t>() = capacity;
	*stream.Extract<std::size_t>() = min_size;
	*stream.Extract<std::size_t>() = min_size_pool;

	auto allocator_min_size = std::min(min_size_pool, 64 * min_size);

	std::shared_ptr<BuddyAllocator> allocator = BuddyAllocator::Create(stream, capacity, allocator_min_size);

	auto buddy_allocator_depth = bit_width(capacity / allocator_min_size) - 1;
	auto buddy_allocator_num_blocks = 1ull << (buddy_allocator_depth + 1);

	Pool *pools = stream.Extract<Pool>(buddy_allocator_num_blocks);

	for (std::size_t i = 0; i < buddy_allocator_num_blocks; ++i)
		pools[i].map = 0;

	return std::shared_ptr<HybridPoolAllocator>(new HybridPoolAllocator(capacity, min_size, min_size_pool, std::move(allocator), pools, stream.GetBuffer()));
}

std::shared_ptr<HybridPoolAllocator> HybridPoolAllocator::Open(StructStream &stream)
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

	return std::shared_ptr<HybridPoolAllocator>(new HybridPoolAllocator(capacity, min_size, min_size_pool, std::move(allocator), pools, stream.GetBuffer()));
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
	DEBUG_PRINT("HybridPoolAllocator::Allocate(" << size << ")");

	size = round_up_to_power_of_2(size);

	if (size < m_MinSize)
		size = m_MinSize;

	if (size >= m_MinSizePool)
	{
		DEBUG_PRINT("size is too large for pools");

		// The size is too large to use pools. Defer to the buddy allocator.
		return m_Allocator->Allocate(size);
	}

	std::size_t level = GetLevelFromSize(size);
	Bucket &bucket = GetBucket(level);

	DEBUG_PRINT("level: " << level);

	// Loop over the pools in the bucket and find a pool with an available slot.
	for (auto it = bucket.rbegin(); it < bucket.rend(); ++it)
	{
		Handle handle = *it;
		Pool &pool = m_Pools[handle];

		DEBUG_PRINT("pool: " << handle << " " << pool.map);

		// Increment the ref counter of the pool before we start messing with it.
		m_Allocator->Acquire(handle);

		auto val_inv = ~(pool.map);

		if (val_inv == 0)
		{
			DEBUG_PRINT("pool is full");

			m_Allocator->Release(handle);

			// No slots available in this pool. Move to the next.
			continue;
		}

		Handle sub_handle = bit_width(val_inv) - 1;
		auto mask = (1ull << sub_handle);

		pool.map |= mask;

		if (~(pool.map) == 0)
		{
			DEBUG_PRINT("pool became full");

			// No slots available in this pool. Move to the
			// The pool is full. Remove it from the bucket.
			bucket.erase(std::next(it).base());
		}

		DEBUG_PRINT("returning " << (handle << 6) + sub_handle);

		// Set the reference count.
		pool.ref_counts[sub_handle].Reset();

		DEBUG_PRINT("Reset reference count to 1");

		return (handle << 6) + sub_handle;
	}

	DEBUG_PRINT("no slot available, allocating new pool.");

	// No slot in any pool was available. Allocate a new pool.
	auto new_handle = m_Allocator->Allocate(size * 64);

	if (new_handle == BuddyAllocator::INVALID_HANDLE)
	{
		throw std::runtime_error("Failed to allocate a new pool.");
	}

	// Increment ref count for the slot in the pool.
	m_Allocator->Acquire(new_handle);

	Pool &pool = m_Pools[new_handle];

	bucket.emplace_back(new_handle);

	// Set the map and reset the reference count of this slot.
	pool.map = 1;
	pool.ref_counts[0].Reset();

	DEBUG_PRINT("set pool parameters and returning " << (new_handle << 6));

	return new_handle << 6;
}

bool HybridPoolAllocator::Acquire(Handle handle)
{
	DEBUG_PRINT("Acquiring " << handle);

	// Get the level of this block.
	std::size_t level = GetLevelFromHandle(handle);

	// Get the size of blocks at this level.
	std::size_t size = m_Capacity >> level;

	if (size >= m_MinSizePool)
	{
		// This is a block in the allocator.
		return m_Allocator->Acquire(handle);
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
	DEBUG_PRINT("Releasing " << handle);

	// Get the level of this block.
	std::size_t level = GetLevelFromHandle(handle);

	// Get the size of blocks at this level.
	std::size_t size = m_Capacity >> level;

	DEBUG_PRINT("Level " << level << ", size " << size);

	if (size >= m_MinSizePool)
	{
		DEBUG_PRINT("Block is in the parent allocator. Releasing it from there.");

		// This is a block in the allocator.
		return m_Allocator->Release(handle);
	}
	else
	{
		DEBUG_PRINT("Block is in one of our pools.");

		// This is a block in one of our pools. Find cache handle and sub handle.
		BuddyAllocator::Handle pool_handle = handle >> 6;
		Handle sub_handle = (handle & ((1 << 6) - 1));
		std::uint64_t mask = 1ull << sub_handle;

		DEBUG_PRINT("Pool handle " << pool_handle << ", sub handle " << sub_handle);
		DEBUG_PRINT("Mask " << mask);

		Pool &pool = m_Pools[pool_handle];

		if (!pool.ref_counts[sub_handle].Decrement())
		{
			DEBUG_PRINT("Block still has references.");

			// Someone else is still owning this slot. Return.
			return false;
		}

		auto &bucket = GetBucket(level);

		// Add the pool on the bucket if it's not entirely full anymore after
		// we free the slot.
		if (~(pool.map) == 0)
		{
			DEBUG_PRINT("Pool will have a new empty slot. Adding back to the bucket.");

			bucket.emplace_back(pool_handle);
		}

		// Update the pool bitmap.
		pool.map &= ~mask;

		// Decrement the ref count of the pool to account for the slot being released.
		m_Allocator->Release(pool_handle);

		if (pool.map == 0)
		{
			DEBUG_PRINT("Pool is now fully empty. Releasing the pool itself.");

			// Release the pool. We're the owner so we are guaranteed to be successful.
			m_Allocator->Release(pool_handle);

			DEBUG_PRINT("Also removing the pool from our bucket.");
			DEBUG_PRINT("Searching for " << pool_handle);
			DEBUG_PRINT("Bucket: ");
			for (auto &pool_handle : bucket)
			{
				DEBUG_PRINT("  " << pool_handle);
			}

			auto it = std::find(bucket.begin(), bucket.end(), pool_handle);

			// Check if we own the pool (ie. if it was in our bucket).
			if (it != bucket.end())
			{
				// Remove the pool from our bucket so that we don't reuse it anymore.
				bucket.erase(it);
			}

			DEBUG_PRINT("Done.");
		}

		DEBUG_PRINT("Successful deallocation.");

		return true;
	}
}

std::size_t HybridPoolAllocator::GetOffset(Handle handle) const
{
	return (handle - (1 << GetLevelFromHandle(handle))) * GetSizeFromHandle(handle);
}

std::size_t HybridPoolAllocator::GetLevelFromHandle(Handle handle) const
{
	return bit_width(handle) - 1;
}

std::size_t HybridPoolAllocator::GetLevelFromSize(std::size_t size) const
{
	return GetLevelFromHandle(m_Capacity / size);
}

std::size_t HybridPoolAllocator::GetSizeFromHandle(Handle handle) const
{
	return m_Capacity >> GetLevelFromHandle(handle);
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
