#include "RingBuffer.h"

#include <cstring>

RingBuffer::RingBuffer(Header *header, char *buffer)
	: m_Buffer(buffer),
	m_BufferSize(header->m_BufferSize),
	m_ValueSize(header->m_ValueSize),
	m_Head(header->m_Head),
	m_Tail(header->m_Tail)
{
}

std::unique_ptr<RingBuffer> RingBuffer::Create(StructStream &stream, std::size_t buffer_size, std::size_t value_size)
{
	auto header = stream.Extract<Header>();
	auto buffer = stream.Extract<char>(buffer_size * value_size);

	header->m_BufferSize = buffer_size;
	header->m_ValueSize = value_size;

	header->m_Head.store(0);
	header->m_Tail.store(0);

	return std::unique_ptr<RingBuffer>(new RingBuffer(header, buffer));
}

std::unique_ptr<RingBuffer> RingBuffer::Open(StructStream &stream)
{
	auto header = stream.Extract<Header>();
	auto buffer = stream.Extract<char>(header->m_BufferSize * header->m_ValueSize);

	return std::unique_ptr<RingBuffer>(new RingBuffer(header, buffer));
}

std::size_t RingBuffer::CalculateMetadataBufferSize(std::size_t buffer_size, std::size_t value_size)
{
	return sizeof(Header) + buffer_size * value_size;
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
