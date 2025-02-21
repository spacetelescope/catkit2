#include "PoolAllocator.h"

#include <algorithm>

const std::uint8_t VERSION[4] = {0, 0, 0, 0};

PoolAllocator::PoolAllocator(SharedState *shared_state, std::atomic<BlockHandle> *next)
	: m_Header(shared_state->header),
	m_Next(next),
	m_Capacity(m_Header.capacity),
	m_Head(m_Header.head),
	ShareableImpl<ShareableType::PoolAllocator>(shared_state, shared_state->header.capacity * sizeof(std::atomic<BlockHandle>))
{
}

void PoolAllocator::GetMemoryLayout(SharedState *shared_state, std::atomic<BlockHandle> **next)
{
	*next = reinterpret_cast<std::atomic<BlockHandle> *>(reinterpret_cast<char *>(shared_state) + sizeof(Header));
}

std::unique_ptr<PoolAllocator> PoolAllocator::Create(SharedState *shared_state, std::uint32_t capacity)
{
	Header *header = &shared_state->header;

	std::atomic<BlockHandle> *next;
	GetMemoryLayout(shared_state, &next);

	// Set version and capacity.
	std::copy(VERSION, VERSION + sizeof(VERSION), header->version);
	header->capacity = capacity;

	// Initialize the linked list.
	header->head.store(0, std::memory_order_relaxed);

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

	return std::unique_ptr<PoolAllocator>(new PoolAllocator(shared_state, next));
}

std::unique_ptr<PoolAllocator> PoolAllocator::Open(SharedState *shared_state)
{
	std::atomic<BlockHandle> *next;
	GetMemoryLayout(shared_state, &next);

	return std::unique_ptr<PoolAllocator>(new PoolAllocator(shared_state, next));
}

std::size_t PoolAllocator::CalculateMetadataBufferSize(std::uint32_t capacity)
{
	std::size_t size = sizeof(Header);
	size += capacity * sizeof(std::atomic<BlockHandle>);

	return size;
}

PoolAllocator::BlockHandle PoolAllocator::Allocate()
{
	BlockHandle head = m_Head.load(std::memory_order_relaxed);
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
	} while (!m_Head.compare_exchange_weak(head, next));

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

	BlockHandle head = m_Head.load(std::memory_order_relaxed);;

	// Push the element back on the front of the linked list.
	do
	{
		m_Next[index] = head;
	} while (!m_Head.compare_exchange_weak(head, index));
}
