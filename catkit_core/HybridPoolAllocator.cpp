#include "HybridPoolAllocator.h"
#include "Util.h"

#include <array>
#include <stdexcept>

const std::array<std::uint8_t, 4> HYBRID_POOL_ALLOCATOR_VERSION = {0, 0, 0, 0};

bool HybridPoolAllocator::Pool::IncrementRefCount()
{
	// Check if the zero-flag was set before incrementing.
	return (next_and_ref_count.fetch_add(1) & REF_COUNT_FLAG) == 0;
}

bool HybridPoolAllocator::Pool::DecrementRefCount()
{
	// Decrement the reference count.
	auto old = next_and_ref_count.fetch_sub(1);

	// Check if we just set the ref count to zero.
	if (old & REF_COUNT_MASK == 1)
	{
		// The counter is now zero. We need to set the zero-flag to indicate this,
		// otherwise it doesn't count. Use a CAS loop for this.
		std::uint64_t desired;
		do
		{
			if (old & ~HANDLE_MASK != 0)
			{
				// Either the zero-flag was set by someone else, or the ref count
				// was incremented by someone else. Either way, we're not the one
				// to set the zero flag.
				return false;
			}

			old &= HANDLE_MASK;
			desired = old | REF_COUNT_FLAG;
		} while (next_and_ref_count.compare_exchange_weak(old, desired));

		// We successfully set the zero-flag.
		return true;
	}

	return false;
}

std::pair<BuddyAllocator::Handle, bool> HybridPoolAllocator::Pool::UnpackNextAndRefCount(std::uint64_t next_and_ref_count)
{
	return {next_and_ref_count >> REF_COUNT_SIZE, next_and_ref_count & REF_COUNT_FLAG};
}

std::uint64_t HybridPoolAllocator::Pool::PackNextAndRefCount(BuddyAllocator::Handle next, std::uint16_t ref_count)
{
	return (next << REF_COUNT_SIZE) | (ref_count & REF_COUNT_MASK);
}

std::uint64_t HybridPoolAllocator::Pool::SetNext(std::uint64_t next_and_ref_count, BuddyAllocator::Handle handle)
{
	return (next_and_ref_count & HANDLE_MASK) | (handle & ~HANDLE_MASK);
}

HybridPoolAllocator::HybridPoolAllocator(std::size_t capacity, std::size_t min_size, std::size_t min_size_pool, std::unique_ptr<BuddyAllocator> allocator, Pool *pools, std::atomic_uint64_t *caches)
	: m_Capacity(capacity), m_MinSize(min_size), m_MinSizePool(min_size_pool), m_Allocator(std::move(allocator)), m_Pools(pools), m_Caches(caches)
{
}

std::unique_ptr<HybridPoolAllocator> HybridPoolAllocator::Create(StructStream &stream, std::size_t capacity, std::size_t min_size, std::size_t min_size_pool)
{
	*stream.Extract<std::array<std::uint8_t, 4>>() = HYBRID_POOL_ALLOCATOR_VERSION;

	*stream.Extract<std::size_t>() = capacity;
	*stream.Extract<std::size_t>() = min_size;
	*stream.Extract<std::size_t>() = min_size_pool;

	auto allocator_min_size = 64 * min_size;

	std::unique_ptr<BuddyAllocator> allocator = BuddyAllocator::Create(stream, capacity, allocator_min_size);

	auto depth = bit_width(capacity / min_size);
	auto buddy_allocator_depth = depth - 6; // 6 = log2(64)
	auto buddy_allocator_num_blocks = 1ull << (buddy_allocator_depth + 1);

	Pool *pools = stream.Extract<Pool>(buddy_allocator_num_blocks);

	auto *caches = stream.Extract<std::atomic_uint64_t>(depth + 1);

	// Initialize the blocks.
	for (std::size_t i = 0; i < buddy_allocator_num_blocks; ++i)
	{
		pools[i].map = 0;
		pools[i].next_and_ref_count = Pool::PackNextAndRefCount(BuddyAllocator::INVALID_HANDLE, 0);
	}

	return std::unique_ptr<HybridPoolAllocator>(new HybridPoolAllocator(capacity, min_size, min_size_pool, std::move(allocator), pools, caches));
}

std::unique_ptr<HybridPoolAllocator> HybridPoolAllocator::Open(StructStream &stream)
{
	CheckVersion(stream, HYBRID_POOL_ALLOCATOR_VERSION);

	auto capacity = *stream.Extract<std::size_t>();
	auto min_size = *stream.Extract<std::size_t>();
	auto min_size_pool = *stream.Extract<std::size_t>();

	auto allocator = BuddyAllocator::Open(stream);

	auto depth = bit_width(capacity / min_size);
	auto buddy_allocator_depth = depth - 6; // 6 = log2(64)
	auto buddy_allocator_num_blocks = 1ull << (buddy_allocator_depth + 1);

	auto pools = stream.Extract<Pool>(buddy_allocator_num_blocks);
	auto caches = stream.Extract<std::atomic_uint64_t>(depth + 1);

	return std::unique_ptr<HybridPoolAllocator>(new HybridPoolAllocator(capacity, min_size, min_size_pool, std::move(allocator), pools, caches));
}

ShareableType HybridPoolAllocator::GetType() const
{
	return ShareableType::HybridPoolAllocator;
}

std::size_t HybridPoolAllocator::GetSharedStateSize(std::size_t capacity, std::size_t min_size)
{
	return 0;
}

HybridPoolAllocator::Handle HybridPoolAllocator::Allocate(std::size_t size)
{
	size = round_up_to_power_of_2(size);

	if (size >= m_MinSizePool)
	{
		// The size is too large to use pools. Defer to the buddy allocator.
		return m_Allocator->Allocate(size);
	}

	std::size_t level = GetLevel(size);
	BuddyAllocator::Handle current = m_Caches[level];

	while (current != BuddyAllocator::INVALID_HANDLE)
	{
		Pool &pool = m_Pools[current];

		auto next_and_ref_count = pool.next_and_ref_count.load(std::memory_order_relaxed);
		auto [next, is_marked] = Pool::UnpackNextAndRefCount(next_and_ref_count);

		if (is_marked)
		{
			// This pool is marked for deletion. Ignore and move to the next.
			current = next;
			continue;
		}

		// Try to allocate from this pool.
		if (!pool.IncrementRefCount())
		{
			// We were unsuccessful in incrementing the reference count.
			// This means that someone else deallocated the last slot in this pool,
			// and is currently deallocating this pool. Move to the next pool.
			current = next;
			continue;
		}

		auto val = pool.map.load(std::memory_order_relaxed);
		Handle sub_handle;
		std::uint64_t mask;

		do
		{
			auto val_inv = ~val;

			if (val_inv == 0)
			{
				// No slots available in this pool. Move to the next.
				break;
			}

			sub_handle = bit_width(val_inv) - 1;
			mask = (1ull << sub_handle);

			val = pool.map.fetch_or(mask, std::memory_order_relaxed);
		} while (val & mask);

		// Check whether we were the one that set the map bit from 0 to 1, which means
		// that our allocation is valid.
		// However, when the map was zero before us, this means that someone else before us
		// removed the last slot and is now / going to deleting that pool from the cache.
		// So our allocation is invalid.
		if (!(val & mask) && val != 0)
		{
			// We successfully allocated from the pool, since we're the one who turned the bit from 0 to 1.
			return (current << 6) + sub_handle;
		}

		// Move to the next block.
		current = next;
	}

	// No slot in any pool was available. Allocate a new pool.
	if (current == INVALID_HANDLE)
	{
		// Allocate a new pool.
		current = m_Allocator->Allocate(size * 64);

		if (current == INVALID_HANDLE)
		{
			throw std::runtime_error("Failed to allocate a new pool.");
		}

		Pool &pool = m_Pools[current];

		// Allocate the first element in this pool for us.
		pool.map.store(1, std::memory_order_relaxed);

		// Use CAS to add the new pool to the list of caches.
		BuddyAllocator::Handle head = m_Caches[level].load(std::memory_order_relaxed);

		do
		{
			pool.next_and_ref_count.store(Pool::PackNextAndRefCount(head, 1), std::memory_order_relaxed);
		} while (!m_Caches[level].compare_exchange_weak(head, current));
	}

	return current << 6;
}

bool HybridPoolAllocator::IncrementRefCount(Handle handle)
{
	return false;
}

bool HybridPoolAllocator::Deallocate(Handle handle)
{
	// Get the level of this block.
	std::size_t level = GetLevel(handle);

	// Get the size of blocks at this level.
	std::size_t size = m_Capacity >> (level - 1);

	if (size >= m_MinSizePool)
	{
		// This is a block in the allocator.
		return m_Allocator->Deallocate(handle);
	}
	else
	{
		// This is a block in one of our pools. Find cache handle and sub handle.
		BuddyAllocator::Handle cache_handle = handle >> 6;
		Handle sub_handle = (handle & ((1 << 6) - 1));
		std::uint64_t mask = 1ull << sub_handle;

		Pool &pool = m_Pools[cache_handle];

		// Update the pool bitmap.
		auto val = pool.map.fetch_and(~mask, std::memory_order_relaxed);

		// Decrement the pool reference count.
		if (!pool.DecrementRefCount())
		{
			// The pool is now empty. Remove it from the cache.
			// The zero-bit is used as the mark, so we don't need to mark the
			// pool for deletion.
			HealCache(level);
		}

		m_Allocator->Deallocate(cache_handle);
	}

	return true;
}

void HybridPoolAllocator::HealCache(std::size_t level)
{
	// TODO
}
