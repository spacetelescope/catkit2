#include "PoolAllocator.h"

#include <algorithm>

const std::uint8_t VERSION[4] = {0, 0, 0, 0};

PoolAllocator::PoolAllocator(Header *header, std::atomic<BlockHandle> *next)
	: m_Header(*header),
	m_Next(next),
	m_Capacity(m_Header.capacity),
	m_Head(m_Header.head)
{
}

void PoolAllocator::GetMemoryLayout(void *metadata_buffer, std::atomic<BlockHandle> **next)
{
	*next = reinterpret_cast<std::atomic<BlockHandle> *>(static_cast<char *>(metadata_buffer) + sizeof(Header));
}

std::shared_ptr<PoolAllocator> PoolAllocator::Create(void *metadata_buffer, std::uint32_t capacity)
{
	Header *header = static_cast<PoolAllocator::Header *>(metadata_buffer);

	std::atomic<BlockHandle> *next;
	GetMemoryLayout(metadata_buffer, &next);

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

	return std::shared_ptr<PoolAllocator>(new PoolAllocator(header, next));
}

std::shared_ptr<PoolAllocator> PoolAllocator::Open(void *metadata_buffer)
{
	Header *header = static_cast<PoolAllocator::Header *>(metadata_buffer);

	std::atomic<BlockHandle> *next;
	GetMemoryLayout(metadata_buffer, &next);

	return std::shared_ptr<PoolAllocator>(new PoolAllocator(header, next));
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
