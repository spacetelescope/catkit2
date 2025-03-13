#include "LocalMemory.h"

LocalMemory::LocalMemory(std::size_t num_bytes)
    : m_Memory(new char[num_bytes]), m_Capacity(num_bytes)
{
}

LocalMemory::~LocalMemory()
{
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
}
