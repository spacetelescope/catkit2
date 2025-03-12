#include "PoolAllocator.h"

#include <algorithm>

const std::array<std::uint8_t, 4> VERSION = {0, 0, 0, 0};

PoolAllocator::PoolAllocator(std::uint32_t capacity, std::atomic<BlockHandle> *head, std::atomic<BlockHandle> *next)
	: m_Capacity(capacity), m_Head(head), m_Next(next)
{
}

std::size_t PoolAllocator::GetSharedStateSize(std::uint32_t capacity)
{
	return 0;
}

std::unique_ptr<PoolAllocator> PoolAllocator::Create(StructStream &stream, std::uint32_t capacity)
{
	// Add padding to ensure consistent alignment from object to object.
	stream.AddPadding<BlockHandle>();

	// Set version and capacity.
	*stream.Extract<std::array<std::uint8_t, 4>>() = VERSION;
	*stream.Extract<std::uint32_t>() = capacity;

	std::atomic<BlockHandle> *head = stream.Extract<std::atomic<BlockHandle>>();
	std::atomic<BlockHandle> *next = stream.Extract<std::atomic<BlockHandle>>(capacity);

	// Initialize the linked list.
	std::uninitialized_default_construct(head, head + 1);
	std::uninitialized_default_construct(next, next + capacity);

	head->store(0, std::memory_order_relaxed);

	for (std::size_t i = 0; i < capacity; ++i)
	{
		if (i == capacity - 1)
		{
			next[i] = INVALID_HANDLE;
		}
		else
		{
			next[i] = i + 1;
		}
	}

	return std::unique_ptr<PoolAllocator>(new PoolAllocator(capacity, head, next));
}

std::unique_ptr<PoolAllocator> PoolAllocator::Open(StructStream &stream)
{
	CheckVersion(stream, VERSION);
	auto capacity = *stream.Extract<std::uint32_t>();

	auto head = stream.Extract<std::atomic<BlockHandle>>();
	auto next = stream.Extract<std::atomic<BlockHandle>>(capacity);

	return std::unique_ptr<PoolAllocator>(new PoolAllocator(capacity, head, next));
}

PoolAllocator::BlockHandle PoolAllocator::Allocate()
{
	BlockHandle head = m_Head->load(std::memory_order_relaxed);
	BlockHandle next;

	// Pop the first element from the linked list.
	do
	{
		// Check if the pool is empty.
		if (head == INVALID_HANDLE)
		{
			return INVALID_HANDLE;
		}

		next = m_Next[head].load(std::memory_order_relaxed);
	} while (!m_Head->compare_exchange_weak(head, next));

	// Return the popped element.
	return head;
}

void PoolAllocator::Deallocate(BlockHandle index)
{
	// Check if the element is within the pool bounds.
	if (index >= m_Capacity)
	{
		return;
	}

	BlockHandle head = m_Head->load(std::memory_order_relaxed);;

	// Push the element back on the front of the linked list.
	do
	{
		m_Next[index] = head;
	} while (!m_Head->compare_exchange_weak(head, index));
}

ShareableType PoolAllocator::GetType() const
{
	return ShareableType::PoolAllocator;
}
