#include "PoolAllocator.h"

#include <algorithm>

const std::uint8_t VERSION[4] = {0, 0, 0, 0};

PoolAllocator::PoolAllocator(void *metadata_buffer)
    : m_Header(*static_cast<Header *>(metadata_buffer)),
                m_Capacity(m_Header.capacity),
                m_Head(m_Header.head),
                m_Next(reinterpret_cast<std::atomic_uint32_t *>(static_cast<char *>(metadata_buffer) + sizeof(Header)))
{
}

void PoolAllocator::Initialize(std::uint32_t capacity)
{
    // Set version and capacity.
    std::copy(VERSION, VERSION + sizeof(VERSION), m_Header.version);
    m_Capacity = capacity;

    // Initialize the linked list.
    m_Head.store(0, std::memory_order_relaxed);

    for (std::size_t i = 0; i < m_Capacity; ++i)
    {
        if (i == m_Capacity - 1)
        {
            m_Next[i] = INVALID_HANDLE;
        }
        else
        {
            m_Next[i] = i + 1;
        }
    }
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
