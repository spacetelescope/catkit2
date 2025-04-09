#include "HybridPoolAllocator.h"
#include "Util.h"

#include <array>

const std::array<std::uint8_t, 4> HYBRID_POOL_ALLOCATOR_VERSION = {0, 0, 0, 0};


HybridPoolAllocator::MarkedHandle::MarkedHandle()
{
}

HybridPoolAllocator::MarkedHandle::MarkedHandle(BuddyAllocator::Handle handle)
	: m_HandleAndMark(handle << 1)
{
}

BuddyAllocator::Handle HybridPoolAllocator::MarkedHandle::GetHandle() const
{
	return m_HandleAndMark >> 1;
}

void HybridPoolAllocator::MarkedHandle::SetHandle(const BuddyAllocator::Handle &handle)
{
	m_HandleAndMark = (handle << 1) | (m_HandleAndMark & 1);
}

bool HybridPoolAllocator::MarkedHandle::IsMarked() const
{
	return m_HandleAndMark & 1;
}

void HybridPoolAllocator::MarkedHandle::Mark()
{
	m_HandleAndMark |= 1;
}

HybridPoolAllocator::HybridPoolAllocator(std::size_t capacity, std::size_t min_size, std::size_t min_size_pool, std::unique_ptr<BuddyAllocator> allocator, Block *blocks, std::atomic<MarkedHandle> *caches)
	: m_Capacity(capacity), m_MinSize(min_size), m_MinSizePool(min_size_pool), m_Allocator(std::move(allocator)), m_Blocks(blocks), m_Caches(caches)
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

	Block *blocks = stream.Extract<Block>(buddy_allocator_num_blocks);

	auto *caches = stream.Extract<std::atomic<MarkedHandle>>(depth + 1);

	// Initialize the blocks.
	for (std::size_t i = 0; i < buddy_allocator_num_blocks; ++i)
	{
		blocks[i].map = 0;
		blocks[i].next = MarkedHandle(BuddyAllocator::INVALID_HANDLE);
	}

	return std::unique_ptr<HybridPoolAllocator>(new HybridPoolAllocator(capacity, min_size, min_size_pool, std::move(allocator), blocks, caches));
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

	auto blocks = stream.Extract<Block>(buddy_allocator_num_blocks);
	auto caches = stream.Extract<std::atomic<MarkedHandle>>(depth + 1);

	return std::unique_ptr<HybridPoolAllocator>(new HybridPoolAllocator(capacity, min_size, min_size_pool, std::move(allocator), blocks, caches));
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
	auto cache_handle = m_Caches[level].load(std::memory_order_relaxed);

	while (cache_handle.GetHandle() != BuddyAllocator::INVALID_HANDLE)
	{
		if (cache_handle.IsMarked())
		{
			// This pool is marked for deletion. Ignore and move to the next.
			cache_handle = m_Blocks[cache_handle.GetHandle()].next.load(std::memory_order_relaxed);
			continue;
		}

		Block &block = m_Blocks[cache_handle.GetHandle()];

		auto val = block.map.load(std::memory_order_relaxed);
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

			sub_handle = (64 - __builtin_clzll(val_inv) - 1);
			mask = (1ull << sub_handle);

			val = block.map.fetch_or(mask, std::memory_order_relaxed);
		} while (val & mask);

		// Check whether we were the one that set the map bit from 0 to 1, which means
		// that our allocation is valid.
		// However, when the map was zero before us, this means that someone else before us
		// removed the last slot and is now / going to deleting that pool from the cache.
		// So our allocation is invalid.
		if (!(val & mask) && val != 0)
		{
			// We successfully allocated from the pool, since we're the one who turned the bit from 0 to 1.
			return (cache_handle.GetHandle() << 6) + sub_handle;
		}

		// Move to the next block.
		cache_handle = m_Blocks[cache_handle.GetHandle()].next.load(std::memory_order_relaxed);
	}

	// No slot in any pool was available. Allocate a new pool.
	if (cache_handle.GetHandle() == INVALID_HANDLE)
	{
		// Allocate a new pool.
		cache_handle = m_Allocator->Allocate(size * 64);

		if (cache_handle.GetHandle() == INVALID_HANDLE)
		{
			throw std::runtime_error("Failed to allocate a new pool.");
		}

		Block &block = m_Blocks[cache_handle.GetHandle()];

		// Allocate the first element in this pool for us.
		block.map.store(1);

		// Use CAS to add the new pool to the list of caches.
		auto head = m_Caches[level].load(std::memory_order_relaxed);

		do
		{
			block.next.store(head, std::memory_order_relaxed);
		} while (!m_Caches[level].compare_exchange_weak(head, cache_handle));
	}

	return cache_handle.GetHandle() << 6;
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

		Block &block = m_Blocks[cache_handle];

		// Update the pool bitmap.
		auto val = block.map.fetch_and(~mask, std::memory_order_relaxed);

		// If this is the last block in the cache, return it to the allocator.
		if (val == mask)
		{
			// Pop the cache from the linked list.
			// First mark the cache as
		}

		m_Allocator->Deallocate(cache_handle);
	}

	return true;
}
