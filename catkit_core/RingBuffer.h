#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include "Shareable.h"

#include <atomic>
#include <cstdlib>

// Single producer, multi-consumer lock-free ring buffer.
class RingBuffer : public Shareable
{
private:
	struct Header
	{
		std::size_t m_BufferSize;
		std::size_t m_ValueSize;

		std::atomic<size_t> m_Head;
		std::atomic<size_t> m_Tail;
	};

	RingBuffer(Header *header, char *buffer);

public:
	static std::shared_ptr<RingBuffer> Create(StructStream &stream, std::size_t buffer_size, std::size_t value_size);
	static std::shared_ptr<RingBuffer> Open(StructStream &stream);

	static std::size_t CalculateMetadataBufferSize(std::size_t buffer_size, std::size_t value_size);

	bool Push(const void* item);
	bool Pop(void *item);

	ShareableType GetType() const override;

private:
	char* m_Buffer;

	std::size_t m_BufferSize;
	std::size_t m_ValueSize;

	std::atomic<size_t> &m_Head;
	std::atomic<size_t> &m_Tail;
};

#endif // RING_BUFFER_H
