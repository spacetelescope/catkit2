#include "LocalMemory.h"

#include <stdexcept>

LocalMemory::LocalMemory(char *memory, std::size_t num_bytes, bool is_owner)
	: Shareable(nullptr), m_Memory(memory), m_Capacity(num_bytes), m_IsOwner(is_owner)
{
}

LocalMemory::~LocalMemory()
{
	if (m_IsOwner)
		delete[] m_Memory;
}

void *LocalMemory::GetAddress(std::size_t offset)
{
	return m_Memory + offset;
}

std::size_t LocalMemory::GetCapacity() const
{
	return m_Capacity;
}

void LocalMemory::WriteReference(StructStream &stream)
{
	*stream.Extract<char *>() = m_Memory;
	*stream.Extract<std::size_t>() = m_Capacity;
	*stream.Extract<int>() = GetProcessId();
}

std::shared_ptr<LocalMemory> LocalMemory::Create(StructStream &stream, std::size_t num_bytes)
{
	// Allocate the memory.
	char *memory = new char[num_bytes];
	auto res = std::shared_ptr<LocalMemory>(new LocalMemory(memory, num_bytes, true));

	// Write metadata to stream.
	*stream.Extract<char *>() = res->m_Memory;
	*stream.Extract<std::size_t>() = num_bytes;
	*stream.Extract<int>() = GetProcessId();

	return std::move(res);
}

std::shared_ptr<LocalMemory> LocalMemory::Create(std::size_t num_bytes)
{
	// Allocate the memory.
	char *memory = new char[num_bytes];
	return std::shared_ptr<LocalMemory>(new LocalMemory(memory, num_bytes, true));
}

std::shared_ptr<LocalMemory> LocalMemory::Open(StructStream &stream)
{
	// Read metadata from stream.
	auto memory = *stream.Extract<char *>();
	auto num_bytes = *stream.Extract<std::size_t>();
	auto pid = *stream.Extract<int>();

	if (pid != GetProcessId())
		throw std::runtime_error("This local memory was created on a different process.");

	return std::shared_ptr<LocalMemory>(new LocalMemory(memory, num_bytes, false));
}

ShareableType LocalMemory::GetType() const
{
	return ShareableType::LocalMemory;
}

MemoryType LocalMemory::GetMemoryType() const
{
	return MemoryType::LocalMemory;
}
