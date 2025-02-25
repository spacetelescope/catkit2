#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include "Shareable.h"

#include <atomic>
#include <iostream>
#include <cstdlib>
#include <cstring>

// Single producer, multi-consumer lock-free ring buffer.
class RingBuffer : public ShareableImpl<ShareableType::RingBuffer>
{
private:
	RingBuffer(SharedState *shared_state);

public:
	static std::unique_ptr<RingBuffer> Create(SharedState *shared_state, std::size_t buffer_size, std::size_t value_size);
	static std::unique_ptr<RingBuffer> Open(SharedState *shared_state);

	static std::size_t CalculateMetadataBufferSize(std::size_t buffer_size, std::size_t value_size);

	bool Push(const void* item);
	bool Pop(void *item);

private:
	char* m_Buffer;

	std::size_t &m_BufferSize;
	std::size_t &m_ValueSize;

	std::atomic<size_t> &m_Head;
	std::atomic<size_t> &m_Tail;
};

template<>
struct SharedStateInternal<ShareableType::RingBuffer>
{
	std::size_t buffer_size;
	std::size_t value_size;

	std::atomic<std::size_t> head;
	std::atomic<std::size_t> tail;
};

#endif // RING_BUFFER_H
