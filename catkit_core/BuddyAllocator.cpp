#include "BuddyAllocator.h"
#include "Util.h"

#include <cstdint>
#include <limits>
#include <type_traits>
#include <array>
#include <iostream>
#include <stdexcept>

//#define DEBUG_PRINT(a) std::cout << a << std::endl
#define DEBUG_PRINT(a)

const std::array<std::uint8_t, 4> BUDDY_ALLOCATOR_VERSION = {0, 0, 0, 0};

const std::uint16_t REF_ZERO = 1ull << 15;
const std::uint16_t OCC = 1ull << 14;
const std::uint16_t OCC_LEFT = 1ull << 13;
const std::uint16_t OCC_RIGHT = 1ull << 12;
const std::uint16_t COAL_LEFT = 1ull << 11;
const std::uint16_t COAL_RIGHT = 1ull << 10;

const std::uint16_t BUSY = (OCC | OCC_LEFT | OCC_RIGHT);
const std::uint16_t REF_MASK = ~(OCC | OCC_LEFT | OCC_RIGHT | COAL_LEFT | COAL_RIGHT);

constexpr inline std::uint16_t CleanCoal(std::uint16_t val, std::size_t child)
{
	return val & ~(COAL_LEFT >> (child & 1));
}

constexpr inline std::uint16_t Mark(std::uint16_t val, std::size_t child)
{
	return val | (OCC_LEFT >> (child & 1));
}

constexpr inline std::uint16_t Unmark(std::uint16_t val, std::size_t child)
{
	return val & ~((OCC_LEFT | COAL_LEFT) >> (child & 1));
}

constexpr inline bool IsCoal(std::uint16_t val, std::size_t child)
{
	return val & (COAL_LEFT >> (child & 1));
}

constexpr inline bool IsOccBuddy(std::uint16_t val, std::size_t child)
{
	return val & (OCC_RIGHT << (child & 1));
}

constexpr inline bool IsCoalBuddy(std::uint16_t val, std::size_t child)
{
	return val & (COAL_RIGHT << (child & 1));
}

constexpr inline bool IsFree(std::uint16_t val)
{
	return ~(val & BUSY);
}

BuddyAllocator::BuddyAllocator(std::size_t capacity, std::size_t min_size, std::atomic_uint16_t *tree, std::atomic_size_t *last_success, std::shared_ptr<Memory> memory_block)
	: Shareable(memory_block), m_Capacity(capacity), m_MinSize(min_size), m_Depth(bit_width(capacity / min_size) - 1), m_Tree(tree), m_LastSuccessfulAllocation(last_success)
{
	// Check that min_size and capacity are powers of two.
	if ((min_size & (min_size - 1)) != 0)
		throw std::runtime_error("Min size must be a power of two.");

	if ((capacity & (capacity - 1)) != 0)
		throw std::runtime_error("Max size must be a power of two.");

	// Check that capacity is greater than or equal to min_size.
	if (capacity < min_size)
		throw std::runtime_error("Max size must be greater than or equal to min size.");
}

std::shared_ptr<BuddyAllocator> BuddyAllocator::Create(StructStream &stream, std::size_t capacity, std::size_t min_size)
{
	*stream.Extract<std::array<std::uint8_t, 4>>() = BUDDY_ALLOCATOR_VERSION;

	*stream.Extract<std::size_t>() = capacity;
	*stream.Extract<std::size_t>() = min_size;

	auto depth = bit_width(capacity / min_size) - 1;

	auto tree = stream.Extract<std::atomic_uint16_t>(1 << (depth + 1));
	auto last_success = stream.Extract<std::atomic_size_t>(depth + 1);

	for (std::size_t i = 0; i < (1 << (depth + 1)); ++i)
	{
		tree[i].store(0);
	}

	for (std::size_t i = 0; i < depth + 1; ++i)
	{
		last_success[i].store((1 << (depth - 1)) - 1);
	}

	return std::shared_ptr<BuddyAllocator>(new BuddyAllocator(capacity, min_size, tree, last_success, stream.GetBuffer()));
}

std::shared_ptr<BuddyAllocator> BuddyAllocator::Open(StructStream &stream)
{
	CheckVersion(stream, BUDDY_ALLOCATOR_VERSION);

	auto capacity = *stream.Extract<std::size_t>();
	auto min_size = *stream.Extract<std::size_t>();

	auto depth = bit_width(capacity / min_size) - 1;

	auto tree = stream.Extract<std::atomic_uint16_t>(1 << (depth + 1));
	auto last_success = stream.Extract<std::atomic_size_t>(depth + 1);

	return std::shared_ptr<BuddyAllocator>(new BuddyAllocator(capacity, min_size, tree, last_success, stream.GetBuffer()));
}

std::size_t BuddyAllocator::GetSharedStateSize(std::size_t capacity, std::size_t min_size)
{
	// Version + padding.
	std::size_t size = sizeof(BUDDY_ALLOCATOR_VERSION) + 4;

	// Max size + depth.
	size += 2 * sizeof(std::size_t);

	auto depth = bit_width(capacity / min_size);

	// Tree.
	size += (1 << (depth + 1)) * sizeof(std::atomic_uint16_t);

	// Last success.
	size += depth * sizeof(std::atomic_size_t);

	return size;
}

BuddyAllocator::Handle BuddyAllocator::Allocate(std::size_t size)
{
	DEBUG_PRINT("Allocating " << size << " bytes.");

	if (size > m_Capacity || size == 0)
		return INVALID_HANDLE;

	size = round_up_to_power_of_2(size);

	if (size < m_MinSize)
	{
		size = m_MinSize;
	}

	Handle begin = m_Capacity / size;
	Handle end = begin << 1;

	auto level = GetLevel(begin);

	DEBUG_PRINT("Level " << level << ".");
	DEBUG_PRINT("Range: " << begin << " to " << end << ".");

	Handle i;
	std::size_t k = 0;

	std::size_t start = m_LastSuccessfulAllocation[level].load(std::memory_order_relaxed) - begin + 1;
	DEBUG_PRINT("Starting search at " << start);

	while (k < (end - begin))
	{
		i = begin + (start + k) % (end - begin);
		DEBUG_PRINT("Checking node " << i << " (k = " << k << ")");

		if (IsFree(m_Tree[i].load(std::memory_order_relaxed)))
		{
			auto failed_at = TryAllocate(i);

			if (failed_at == INVALID_HANDLE)
			{
				DEBUG_PRINT("Successful at node " << i);
				DEBUG_PRINT("Ref count = " << (m_Tree[i].load(std::memory_order_relaxed) & REF_MASK));

				m_LastSuccessfulAllocation[level].store(i, std::memory_order_relaxed);
				return i;
			}
			else
			{
				auto d = level - GetLevel(failed_at);
				k += ((failed_at + 1) << d) - i;

				DEBUG_PRINT("Failed at " << failed_at);
				DEBUG_PRINT("d = " << d << ".");
				DEBUG_PRINT("Advancing to " << i << " (k = " << k << ").");
			}
		}
	}

	return INVALID_HANDLE;
}

bool BuddyAllocator::Acquire(Handle handle)
{
	DEBUG_PRINT("Acquiring handle " << handle);

	DEBUG_PRINT("Ref count = " << ((m_Tree[handle].load(std::memory_order_relaxed) & REF_MASK) + 1));

	// Increment the reference counter, but check for zero reference bit.
	return (m_Tree[handle].fetch_add(1, std::memory_order_relaxed) & REF_ZERO) == 0;
}

bool BuddyAllocator::Release(Handle handle)
{
	DEBUG_PRINT("Releasing handle " << handle);

	// Decrement the ref counter.
	auto old_val = m_Tree[handle].fetch_sub(1, std::memory_order_relaxed);

	DEBUG_PRINT("Decremented ref counter");
	DEBUG_PRINT("Ref count = " << (m_Tree[handle].load(std::memory_order_relaxed) & REF_MASK));

	if ((old_val & REF_MASK) == 1)
	{
		// The counter should now be zero. Let's try to set the REF_ZERO bit to indicate this.
		std::uint16_t expected = old_val - 1;

		do
		{
			std::uint16_t new_val = expected | REF_ZERO;

			bool success = m_Tree[handle].compare_exchange_weak(expected, new_val, std::memory_order_relaxed);

			// If the replace was successful, we were the one setting the ref count to zero.
			// So let's free the node.
			if (success)
				break;

			// If we were unsuccesful, let's look if someone increased the ref count.
			// Incrementing linearizes before decrement, so the counter wasn't "actually" zero.
			// So we shouldn't free the node.
			// If someone modified the other bits, we should try again to set REF_ZERO.
			if (expected & REF_MASK)
				return false;
		} while (true);
	}
	else
	{
		// Reference count is not zero, so we can't free the node.
		return false;
	}

	FreeNode(handle, 0);

	//m_LastSuccessfulAllocation[GetLevel(handle)].store(handle, std::memory_order_relaxed);

	return true;
}

std::size_t BuddyAllocator::GetOffset(Handle handle) const
{
	return (handle - (1 << GetLevel(handle))) * GetSize(handle);
}

BuddyAllocator::Handle BuddyAllocator::TryAllocate(Handle n)
{
	DEBUG_PRINT("Trying to allocate node " << n);

	std::uint16_t expected = 0;

	// Try to own the node, and set the ref_count to one.
	if (!m_Tree[n].compare_exchange_strong(expected, BUSY + 1, std::memory_order_relaxed))
	{
		DEBUG_PRINT("Failed to allocate node " << n);
		return n;
	}

	DEBUG_PRINT("Setting node " << n << " and all ancestors to busy.");

	auto current = n;
	auto level = GetLevel(current);

	while (level > 0)
	{
		auto child = current;
		current = current >> 1;
		level--;

		std::uint16_t curr_val = m_Tree[current].load(std::memory_order_relaxed);
		std::uint16_t new_val;

		do
		{
			if (curr_val & OCC)
			{
				DEBUG_PRINT("Failed on node " << current << ". Rewinding.");

				FreeNode(n, level + 1);
				return current;
			}

			new_val = Mark(CleanCoal(curr_val, child), child);
		} while (!m_Tree[current].compare_exchange_weak(curr_val, new_val, std::memory_order_relaxed));
	}

	return INVALID_HANDLE;
}

void BuddyAllocator::FreeNode(Handle n, std::size_t upper_bound)
{
	Handle current = n >> 1;
	Handle runner = n;
	auto level = GetLevel(runner);

	DEBUG_PRINT("Marking all ancestors of " << n << " at level " << GetLevel(n) << ".");

	// Phase 1: mark all ancestors of the node as coalescing.
	while (level > upper_bound)
	{
		auto coal_bit = COAL_LEFT >> (runner & 1);
		auto old_val = m_Tree[current].fetch_or(coal_bit, std::memory_order_relaxed);

		DEBUG_PRINT("Marked node " << current << " as coalescing.");

		if (IsOccBuddy(old_val, runner) && !IsCoalBuddy(old_val, runner))
			break;

		runner = current;
		current = current >> 1;
		level--;
	}

	DEBUG_PRINT("Mark node " << n << " as free");

	// Phase 2: mark the node as free.
	m_Tree[n].store(0, std::memory_order_relaxed);

	DEBUG_PRINT("Unmark all ancestors of " << n << ".");

	// Phase 3: reset the coalescing bit for all ancestors.
	if (GetLevel(n) != upper_bound)
		Unmark(n, upper_bound);
}

void BuddyAllocator::Unmark(Handle n, std::size_t upper_bound)
{
	Handle current = n;
	Handle child;
	auto level = GetLevel(n);

	std::uint16_t curr_val;
	std::uint16_t new_val;

	do
	{
		child = current;
		current = current >> 1;
		level--;

		curr_val = m_Tree[current].load(std::memory_order_relaxed);

		do
		{
			if (!IsCoal(curr_val, child))
			{
				DEBUG_PRINT("Stopped due to missing COAL flag on node " << current << " and child " << child);

				return;
			}

			new_val = ::Unmark(curr_val, child);

			DEBUG_PRINT("Unmarked node " << current << " as coalescing.");
		} while (!m_Tree[current].compare_exchange_weak(curr_val, new_val, std::memory_order_relaxed));

	} while (level > upper_bound && !IsOccBuddy(new_val, child));
}

inline std::size_t BuddyAllocator::GetLevel(Handle handle) const
{
	return bit_width(handle) - 1;
}

inline std::size_t BuddyAllocator::GetSize(Handle handle) const
{
	return m_Capacity >> GetLevel(handle);
}

ShareableType BuddyAllocator::GetType() const
{
	return ShareableType::BuddyAllocator;
}

void BuddyAllocator::PrintState() const
{
	std::cout << "Tree: ";
	for (std::size_t level = 1; level < m_Depth + 1; ++level)
	{
		std::cout << "\nLevel " << level << ": " << std::endl;

		Handle begin = 1 << (level - 1);
		Handle end = 1 << level;

		for (Handle i = begin; i < end; ++i)
		{
			auto val = m_Tree[i].load(std::memory_order_relaxed);
			if (val == 0)
				continue;

			bool occ = val & OCC;
			bool occ_right = val & OCC_RIGHT;
			bool occ_left = val & OCC_LEFT;
			bool coal_right = val & COAL_RIGHT;
			bool coal_left = val & COAL_LEFT;

			std::cout << "Node " << i << ": " << std::endl;

			if (occ)
				std::cout << "  Occupied" << std::endl;
			if (occ_right)
				std::cout << "  Occupied right" << std::endl;
			if (occ_left)
				std::cout << "  Occupied left" << std::endl;
			if (coal_right)
				std::cout << "  Coalesced right" << std::endl;
			if (coal_left)
				std::cout << "  Coalesced left" << std::endl;

			std::cout << std::endl;
		}
	}
}

size_t BuddyAllocator::GetUsage() const
{
	size_t used = 0;

	for (size_t level = 1; level < m_Depth; ++level)
	{
		Handle begin = 1 << (level - 1);
		Handle end = 1 << level;

		size_t size = GetSize(begin);

		for (Handle i = begin; i < end; ++i)
		{
			auto val = m_Tree[i].load(std::memory_order_relaxed);

			if (val & OCC)
				used += size;
		}
	}

	return used;
}

size_t BuddyAllocator::GetCapacity() const
{
	return m_Capacity;
}
