#include "PoolAllocator.h"

#include <algorithm>
#include <stdexcept>

const std::array<std::uint8_t, 4> VERSION = {0, 0, 0, 0};

PoolAllocator::PoolAllocator(std::uint32_t capacity, std::atomic<BlockHandle> *head, std::atomic<BlockHandle> *next, std::atomic_size_t *ref_count)
	: m_Capacity(capacity), m_Head(head), m_Next(next), m_RefCount(ref_count)
{
}

std::size_t PoolAllocator::GetSharedStateSize(std::uint32_t capacity)
{
	std::size_t size = sizeof(uint32_t) + sizeof(std::atomic<BlockHandle>);
	size += sizeof(std::atomic<BlockHandle>) * capacity;
	size += sizeof(size_t);
	size += sizeof(std::atomic_size_t) * capacity;

	return size;
}

std::shared_ptr<PoolAllocator> PoolAllocator::Create(StructStream &stream, std::uint32_t capacity)
{
	// Add padding to ensure consistent alignment from object to object.
	stream.AddPadding<BlockHandle>();

	// Set version and capacity.
	*stream.Extract<std::array<std::uint8_t, 4>>() = VERSION;
	*stream.Extract<std::uint32_t>() = capacity;

	std::atomic<BlockHandle> *head = stream.Extract<std::atomic<BlockHandle>>();
	std::atomic<BlockHandle> *next = stream.Extract<std::atomic<BlockHandle>>(capacity);
	std::atomic_size_t *ref_count = stream.Extract<std::atomic_size_t>(capacity);

	// Initialize the linked list.
	std::uninitialized_default_construct(head, head + 1);
	std::uninitialized_default_construct(next, next + capacity);

	head->store(0, std::memory_order_relaxed);

	for (std::size_t i = 0; i < capacity; ++i)
	{
		next[i].store(i + 1, std::memory_order_relaxed);
		ref_count[i].store(0, std::memory_order_relaxed);
	}
	next[capacity - 1].store(INVALID_HANDLE, std::memory_order_relaxed);

	return std::shared_ptr<PoolAllocator>(new PoolAllocator(capacity, head, next, ref_count));
}

std::shared_ptr<PoolAllocator> PoolAllocator::Open(StructStream &stream)
{
	CheckVersion(stream, VERSION);
	auto capacity = *stream.Extract<std::uint32_t>();

	auto head = stream.Extract<std::atomic<BlockHandle>>();
	auto next = stream.Extract<std::atomic<BlockHandle>>(capacity);
	auto *ref_count = stream.Extract<std::atomic_size_t>(capacity);

	return std::shared_ptr<PoolAllocator>(new PoolAllocator(capacity, head, next, ref_count));
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

	// Increase the reference count.
	m_RefCount[head].fetch_add(1, std::memory_order_relaxed);

	// Return the popped element.
	return head;
}

bool PoolAllocator::Acquire(BlockHandle index)
{
	if (index >= m_Capacity)
	{
		return false;
	}

	if (m_RefCount[index].fetch_add(1, std::memory_order_relaxed) == 0)
	{
		// The reference count was 0, so we erroneously increased the ref count and
		// someone else is deallocating the element. Undo the increment and return.
		m_RefCount[index].fetch_sub(1, std::memory_order_relaxed);
		return false;
	};

	return true;
}

bool PoolAllocator::Release(BlockHandle index)
{
	// Check if the element is within the pool bounds.
	if (index >= m_Capacity)
	{
		return false;
	}

	size_t old_ref_count = m_RefCount[index].fetch_sub(1, std::memory_order_relaxed);

	if (old_ref_count != 1)
	{
		// The reference count is not yet zero, so do not deallocate.
		return false;
	}

	if (old_ref_count == 0)
	{
		// Something went horribly wrong with reference counting. Reset the ref count and raise an exception.
		m_RefCount[index].fetch_add(1, std::memory_order_relaxed);

		throw std::runtime_error("A double-free occurred.");
	}

	BlockHandle head = m_Head->load(std::memory_order_relaxed);;

	// Push the element back on the front of the linked list.
	do
	{
		m_Next[index] = head;
	} while (!m_Head->compare_exchange_weak(head, index));

	return true;
}

ShareableType PoolAllocator::GetType() const
{
	return ShareableType::PoolAllocator;
}
