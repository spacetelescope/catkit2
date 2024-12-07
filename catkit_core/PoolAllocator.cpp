#include "PoolAllocator.h"

PoolAllocator::PoolAllocator(void *buffer, std::size_t capacity)
    : m_Head(static_cast<std::atomic_size_t *>(buffer)), m_Next(static_cast<std::atomic_size_t *>(buffer) + 1), m_Capacity(capacity)
{
}

void PoolAllocator::Initialize()
{
    // Initialize the linked list.
    for (std::size_t i = 0; i < m_Capacity; ++i)
    {
        if (i == m_Capacity - 1)
        {
            m_Next[i] = -1;
        }
        else
        {
            m_Next[i] = i + 1;
        }
    }
}

std::size_t PoolAllocator::CalculateBufferSize(std::size_t capacity)
{
    return sizeof(std::atomic_size_t) * (capacity + 1);
}

std::size_t PoolAllocator::Allocate()
{
    std::size_t head;
    std::size_t next;

    // Pop the first element from the linked list.
    do
    {
        head = m_Head->load(std::memory_order_relaxed);

        // Check if the pool is empty.
        if (head == -1)
        {
            return -1;
        }

        next = m_Next[head].load(std::memory_order_relaxed);
    } while (!m_Head->compare_exchange_weak(head, next));

    // Return the popped element.
    return head;
}

void PoolAllocator::Deallocate(std::size_t index)
{
    // Check if the element is within the pool bounds.
    if (index >= m_Capacity)
    {
        return;
    }

    std::size_t head;

    // Push the element back on the front of the linked list.
    do
    {
        head = m_Head->load(std::memory_order_relaxed);
        m_Next[index] = head;
    } while (!m_Head->compare_exchange_weak(head, index));
}
