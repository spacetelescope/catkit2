#include "BuddyAllocator.h"

#include <cstdint>
#include <limits>
#include <type_traits>
#include <array>

const std::array<std::uint8_t, 4> BUDDY_ALLOCATOR_VERSION = {0, 0, 0, 0};

// Cross-platform implementation of std::bit_width() (in absence of C++20)
template <typename T>
constexpr int bit_width(T x)
{
	static_assert(std::is_integral_v<T> && std::is_unsigned_v<T>, "bit_width requires an unsigned integral type");

	if (x == 0)
		return 0;

#if defined(__GNUC__) || defined(__clang__)
	return std::numeric_limits<T>::digits - __builtin_clz(x);
#elif defined(_MSC_VER)
	unsigned long index;
	_BitScanReverse(&index, x);
	return index + 1;
#else
	// Portable fallback
	int width = 0;

	while (x)
	{
		x >>= 1;
		++width;
	}

	return width;
#endif
}

const std::uint8_t OCC_RIGHT = 0x1;
const std::uint8_t OCC_LEFT = 0x2;
const std::uint8_t COAL_RIGHT = 0x4;
const std::uint8_t COAL_LEFT = 0x8;
const std::uint8_t OCC = 0x10;
const std::uint8_t BUSY = (OCC | OCC_LEFT | OCC_RIGHT);

constexpr inline std::uint8_t CleanCoal(std::uint8_t val, std::size_t child)
{
	return val & ~(COAL_LEFT >> (child & 1));
}

constexpr inline std::uint8_t Mark(std::uint8_t val, std::size_t child)
{
	return val | (OCC_LEFT >> (child & 1));
}

constexpr inline std::uint8_t Unmark(std::uint8_t val, std::size_t child)
{
	return val & ~((OCC_LEFT | COAL_LEFT) >> (child & 1));
}

constexpr inline bool IsCoal(std::uint8_t val, std::size_t child)
{
	return val & (COAL_LEFT >> (child & 1));
}

constexpr inline bool IsOccBuddy(std::uint8_t val, std::size_t child)
{
	return val & (OCC_RIGHT << (child & 1));
}

constexpr inline bool IsCoalBuddy(std::uint8_t val, std::size_t child)
{
	return val & (COAL_RIGHT << (child & 1));
}

constexpr inline bool IsFree(std::uint8_t val)
{
	return ~(val & BUSY);
}

BuddyAllocator::BuddyAllocator(std::size_t max_size, std::size_t depth, std::atomic_uint8_t *tree)
	: m_MaxSize(max_size), m_Depth(depth), m_Tree(tree)
{
}

std::unique_ptr<BuddyAllocator> BuddyAllocator::Create(StructStream &stream, std::size_t max_size, std::size_t depth)
{
	*stream.Extract<std::array<std::uint8_t, 4>>() = BUDDY_ALLOCATOR_VERSION;

	*stream.Extract<std::size_t>() = max_size;
	*stream.Extract<std::size_t>() = depth;
	auto tree = stream.Extract<std::atomic_uint8_t>(1 << (depth + 1));

	return std::unique_ptr<BuddyAllocator>(new BuddyAllocator(max_size, depth, tree));
}

std::unique_ptr<BuddyAllocator> BuddyAllocator::Open(StructStream &stream)
{
	CheckVersion(stream, BUDDY_ALLOCATOR_VERSION);

	auto max_size = *stream.Extract<std::size_t>();
	auto depth = *stream.Extract<std::size_t>();

	auto tree = stream.Extract<std::atomic_uint8_t>(1 << (depth + 1));

	return std::unique_ptr<BuddyAllocator>(new BuddyAllocator(max_size, depth, tree));
}

std::size_t BuddyAllocator::GetSharedStateSize(std::size_t max_size, std::size_t depth)
{
	// Version + padding.
	std::size_t size = sizeof(BUDDY_ALLOCATOR_VERSION) + 4;

	// Max size + depth.
	size += 2 * sizeof(std::size_t);

	// Tree.
	size += (1 << (depth + 1)) * sizeof(std::atomic_uint8_t);

	return size;
}

BuddyAllocator::Handle BuddyAllocator::Allocate(std::size_t size)
{
	if (size > m_MaxSize || size == 0)
		return INVALID_HANDLE;

	std::size_t level = bit_width(m_MaxSize / size) - 1;
	if (level > m_Depth)
	{
		level = m_Depth;
	}

	Handle begin = 1 << (level - 1);
	Handle end = 1 << level;

	for (Handle i = begin; i < end; ++i)
	{
		if (IsFree(m_Tree[i]))
		{
			auto failed_at = TryAllocate(i);
			if (!failed_at)
			{
				return i;
			}
			else
			{
				auto d = 1 << (GetLevel(i) - GetLevel(failed_at));
				i = (failed_at + 1) * d;
			}
		}
	}

	return INVALID_HANDLE;
}

void BuddyAllocator::Deallocate(Handle handle)
{
	FreeNode(handle, m_Depth);
}

std::size_t BuddyAllocator::GetOffset(Handle handle) const
{
	return (handle - (1 >> GetLevel(handle))) * GetSize(handle);
}

BuddyAllocator::Handle BuddyAllocator::TryAllocate(Handle n)
{
	std::uint8_t expected = 0;

	if (!m_Tree[n].compare_exchange_strong(expected, BUSY))
	{
		return n;
	}

	auto current = n;

	while (GetLevel(current) > m_Depth)
	{
		auto child = current;
		current = current >> 1;

		std::uint8_t curr_val = m_Tree[current].load(std::memory_order_relaxed);
		std::uint8_t new_val;

		do
		{
			if (curr_val & OCC)
			{
				FreeNode(n, GetLevel(child));
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

	// Phase 1: mark all ancestors of the node as coalescing.
	while (GetLevel(runner) > upper_bound)
	{
		auto coal_bit = COAL_LEFT >> (current & 1);
		auto old_val = m_Tree[n].fetch_or(coal_bit, std::memory_order_relaxed);

		if (IsOccBuddy(old_val, runner) && !IsCoalBuddy(old_val, runner))
			break;

		runner = current;
		current = current >> 1;
	}

	// Phase 2: mark the node as free.
	m_Tree[n].store(0, std::memory_order_relaxed);

	// Phase 3: reset the coalescing bit for all ancestors.
	if (n != upper_bound)
		Unmark(n, upper_bound);
}

void BuddyAllocator::Unmark(Handle n, std::size_t upper_bound)
{
	Handle current = n;
	Handle child;

	std::uint8_t curr_val;
	std::uint8_t new_val;

	do
	{
		child = current;
		current = current >> 1;

		curr_val = m_Tree[current].load(std::memory_order_relaxed);

		do
		{
			if (!IsCoal(curr_val, child))
				return;

			new_val = ::Unmark(curr_val, child);
		} while (m_Tree[current].compare_exchange_weak(curr_val, new_val, std::memory_order_relaxed));

	} while (GetLevel(current) > upper_bound && !IsOccBuddy(new_val, child));
}

inline std::size_t BuddyAllocator::GetLevel(Handle handle) const
{
	return bit_width(handle) - 1;
}

inline std::size_t BuddyAllocator::GetSize(Handle handle) const
{
	return m_MaxSize >> GetLevel(handle);
}

ShareableType BuddyAllocator::GetType() const
{
	return ShareableType::BuddyAllocator;
}
