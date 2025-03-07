#include "PoolAllocator.h"

#include <algorithm>

const std::array<std::uint8_t, 4> VERSION = {0, 0, 0, 0};

PoolAllocator::PoolAllocator(StructStream &stream, std::uint32_t capacity)
{
	m_Version = stream.Extract<std::array<std::uint8_t, 4>>();
	m_Capacity = stream.Extract<std::uint32_t>();
	m_Head = stream.Extract<std::atomic<BlockHandle>>();
	m_Next = stream.Extract<std::atomic<BlockHandle>>(capacity);
}

std::size_t PoolAllocator::GetMemorySize(std::uint32_t capacity)
{
	auto stream = StructStream(nullptr);
	PoolAllocator(stream, capacity);

	return stream.GetOffset();
}

std::unique_ptr<PoolAllocator> PoolAllocator::Create(StructStream &stream, std::uint32_t capacity)
{
	auto res = std::unique_ptr<PoolAllocator>(new PoolAllocator(stream, capacity));

	// Set version and capacity.
	*res->m_Version = VERSION;
	*res->m_Capacity = capacity;

	// Initialize the linked list.
	std::construct_at(res->m_Head);
	res->m_Head->store(0, std::memory_order_relaxed);

	for (std::size_t i = 0; i < capacity; ++i)
	{
		std::construct_at(&res->m_Next[i]);

		if (i == capacity - 1)
		{
			res->m_Next[i] = INVALID_HANDLE;
		}
		else
		{
			res->m_Next[i] = i + 1;
		}
	}

	return res;
}

std::unique_ptr<PoolAllocator> PoolAllocator::Open(StructStream &stream)
{
	StructStream stream_copy = stream;
	CheckVersion(stream_copy, VERSION);

	auto capacity = *stream_copy.Extract<std::uint32_t>();

	return std::unique_ptr<PoolAllocator>(new PoolAllocator(stream, capacity));
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
	if (index >= *m_Capacity)
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
