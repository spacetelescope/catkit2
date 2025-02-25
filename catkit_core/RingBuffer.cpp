#include "RingBuffer.h"

RingBuffer::RingBuffer(SharedState *shared_state)
    : ShareableImpl(shared_state, shared_state->buffer_size * shared_state->value_size),
    m_Buffer(reinterpret_cast<char *>(shared_state) + sizeof(SharedState)),
    m_BufferSize(shared_state->buffer_size),
    m_ValueSize(shared_state->value_size),
    m_Head(shared_state->head),
    m_Tail(shared_state->tail)
{
}

std::unique_ptr<RingBuffer> RingBuffer::Create(SharedState *shared_state, std::size_t buffer_size, std::size_t value_size)
{
    shared_state->buffer_size = buffer_size;
    shared_state->value_size = value_size;
    shared_state->head = 0;
    shared_state->tail = 0;

    return std::unique_ptr<RingBuffer>(new RingBuffer(shared_state));
}

std::unique_ptr<RingBuffer> RingBuffer::Open(SharedState *shared_state)
{
    return std::unique_ptr<RingBuffer>(new RingBuffer(shared_state));
}

std::size_t RingBuffer::CalculateMetadataBufferSize(std::size_t buffer_size, std::size_t value_size)
{
    return sizeof(SharedState) + buffer_size * value_size;
}

bool RingBuffer::Push(const void *item)
{
    size_t current_head = m_Head.load();
    size_t next_head = (current_head + 1) % m_BufferSize;

    // Check if the buffer is full.
    if (next_head == m_Tail.load())
        return false;

    // Write item and update head atomically.
    std::memcpy(m_Buffer + current_head * m_ValueSize, item, m_ValueSize);

    m_Head.store(next_head);

    return true;
}

bool RingBuffer::Pop(void *item)
{
    while (true)
    {
        size_t current_tail = m_Tail.load();

        // Check if the buffer is empty.
        if (current_tail == m_Head.load())
            return false;

        // Copy the item.
        std::memcpy(item, m_Buffer + current_tail * m_ValueSize, m_ValueSize);

        // Update the tail.
        if (!m_Tail.compare_exchange_weak(current_tail, (current_tail + 1) % m_BufferSize))
        {
            // Another thread updated the tail, try again.
            continue;
        }
    }

    // We successfully updated the tail.
    return true;
}
